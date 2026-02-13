import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set

import requests

from servus.config import CONFIG
from servus.integrations.rippling import RipplingClient
from servus.models import UserProfile

logger = logging.getLogger("servus.freshservice")

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ONBOARDING_KEYWORDS = ("onboard", "new hire")
OFFBOARDING_KEYWORDS = (
    "offboard",
    "termination",
    "terminate",
    "deprovision",
    "departure",
    "separation",
)


def fetch_ticket_data(ticket_id):
    """
    Fetches ticket from Freshservice, parses body, and enriches with Rippling data.
    """
    ticket = _fetch_ticket(ticket_id)
    if not ticket:
        return None

    description = ticket.get("description_text") or ticket.get("description") or ""

    try:
        # 1. Regex Parse (The "New Hire" Email format)
        # Matches: "employee - [Name] has been"
        name_match = re.search(r"employee - (.*?) has been", description, re.IGNORECASE)
        date_match = re.search(r"start date of: (.*?)\s*$", description, re.MULTILINE | re.IGNORECASE)

        guessed_email = None
        first_name = ""
        last_name = ""
        start_date = date_match.group(1).strip() if date_match else None

        if name_match:
            full_name = name_match.group(1).strip()
            parts = [part for part in full_name.split(" ") if part]
            if parts:
                first_name = parts[0]
                last_name = " ".join(parts[1:]) if len(parts) > 1 else "Unknown"
                guessed_email = f"{first_name}.{last_name}@boom.aero".lower()
        else:
            logger.warning("Could not parse employee name from ticket #%s; trying email extraction.", ticket_id)

        # 2. Enrichment (preferred source of truth)
        rippling_client = RipplingClient()
        ticket_emails = extract_ticket_emails(ticket_id)
        if guessed_email:
            rippling_profile = rippling_client.find_user_by_email(guessed_email)
            if rippling_profile:
                logger.info("✅ Found match in Rippling: %s", rippling_profile.email)
                return rippling_profile

        for email in ticket_emails:
            rippling_profile = rippling_client.find_user_by_email(email)
            if rippling_profile:
                logger.info("✅ Found match in Rippling via ticket email: %s", rippling_profile.email)
                return rippling_profile

        # 3. Fallback profile from ticket data.
        fallback_email = guessed_email or next(iter(ticket_emails), None)
        if not fallback_email:
            logger.error("Could not derive an email from ticket #%s.", ticket_id)
            return None

        if not first_name or not last_name:
            local_part = fallback_email.split("@")[0]
            parts = [part for part in local_part.replace("-", ".").split(".") if part]
            first_name = first_name or (parts[0].capitalize() if parts else "Unknown")
            last_name = last_name or (parts[-1].capitalize() if len(parts) > 1 else "Unknown")

        logger.warning(
            "⚠️ Could not enrich %s from Rippling. Falling back to ticket-derived defaults.",
            fallback_email,
        )
        return UserProfile(
            first_name=first_name,
            last_name=last_name,
            work_email=fallback_email,
            personal_email=None,
            department="Engineering",
            title="Unknown",
            employment_type="Full-Time",
            start_date=start_date,
            location="US",
        )
    except Exception as exc:
        logger.error("Error processing ticket %s: %s", ticket_id, exc)
        return None


def scan_for_onboarding_tickets(minutes_lookback=60):
    """
    Scans Freshservice for recent onboarding-related tickets.
    Returns a list of ticket IDs.
    """
    return _scan_tickets_by_keywords(minutes_lookback, ONBOARDING_KEYWORDS, label="onboarding")


def scan_for_offboarding_tickets(minutes_lookback=60):
    """
    Scans Freshservice for recent offboarding-related tickets.
    Returns a list of ticket IDs.
    """
    return _scan_tickets_by_keywords(minutes_lookback, OFFBOARDING_KEYWORDS, label="offboarding")


def map_ticket_ids_by_email(ticket_ids: Iterable[object]) -> Dict[str, str]:
    """
    Builds email -> ticket_id mapping for candidate lifecycle tickets.
    First-seen ticket wins to keep mapping deterministic.
    """
    mapping: Dict[str, str] = {}
    for ticket_id in ticket_ids:
        normalized_id = str(ticket_id).strip()
        if not normalized_id:
            continue
        for email in extract_ticket_emails(normalized_id):
            mapping.setdefault(email, normalized_id)
    return mapping


def extract_ticket_emails(ticket_id: object) -> List[str]:
    """
    Extract candidate work emails from ticket metadata/subject/body.
    """
    ticket = _fetch_ticket(ticket_id)
    if not ticket:
        return []

    candidates: Set[str] = set()

    for key in ("email", "requester_email", "responder_email"):
        _add_email(candidates, ticket.get(key))

    requester = ticket.get("requester")
    if isinstance(requester, dict):
        _add_email(candidates, requester.get("primary_email"))
        _add_email(candidates, requester.get("email"))

    for key in ("subject", "description_text", "description"):
        candidates.update(_extract_emails_from_text(ticket.get(key)))

    custom_fields = ticket.get("custom_fields")
    if isinstance(custom_fields, dict):
        for value in custom_fields.values():
            if isinstance(value, str):
                candidates.update(_extract_emails_from_text(value))

    return sorted(candidates)


def _scan_tickets_by_keywords(minutes_lookback, keywords, *, label):
    domain = CONFIG.get("FRESHSERVICE_DOMAIN")
    api_key = CONFIG.get("FRESHSERVICE_API_KEY")
    if not domain or not api_key:
        logger.warning("Freshservice config missing; cannot scan %s tickets.", label)
        return []

    start_time = (datetime.utcnow() - timedelta(minutes=minutes_lookback)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://{domain}/api/v2/tickets?updated_since={start_time}&order_by=created_at&order_type=desc"

    logger.info("🔍 Freshservice: Scanning for %s tickets updated since %s...", label, start_time)
    matches = []
    try:
        resp = requests.get(url, auth=(api_key, "X"), timeout=15)
        if resp.status_code != 200:
            logger.error("❌ Freshservice Scan Error (%s): %s", resp.status_code, resp.text)
            return []

        for ticket in resp.json().get("tickets", []):
            subject = str(ticket.get("subject") or "")
            description = str(ticket.get("description_text") or ticket.get("description") or "")
            haystack = f"{subject}\n{description}".lower()
            if any(keyword in haystack for keyword in keywords):
                ticket_id = ticket.get("id")
                if ticket_id is None:
                    continue
                logger.info("   found candidate ticket: #%s - %s", ticket_id, subject)
                matches.append(str(ticket_id))
    except Exception as exc:
        logger.error("❌ Freshservice Scan Error: %s", exc)
    return matches


def _fetch_ticket(ticket_id) -> Optional[Dict[str, object]]:
    domain = CONFIG.get("FRESHSERVICE_DOMAIN")
    api_key = CONFIG.get("FRESHSERVICE_API_KEY")
    if not domain or not api_key:
        logger.error("Freshservice config missing.")
        return None

    normalized_id = str(ticket_id).strip()
    if not normalized_id:
        return None

    url = f"https://{domain}/api/v2/tickets/{normalized_id}"
    try:
        resp = requests.get(url, auth=(api_key, "X"), timeout=15)
        if resp.status_code != 200:
            logger.error("Freshservice API Error for ticket %s: %s", normalized_id, resp.status_code)
            return None
        ticket = resp.json().get("ticket")
        return ticket if isinstance(ticket, dict) else None
    except Exception as exc:
        logger.error("Freshservice ticket fetch failed for %s: %s", normalized_id, exc)
        return None


def _extract_emails_from_text(raw_text) -> Set[str]:
    text = str(raw_text or "")
    return {email.lower() for email in EMAIL_REGEX.findall(text)}


def _add_email(bucket: Set[str], raw_value):
    value = str(raw_value or "").strip().lower()
    if not value:
        return
    if EMAIL_REGEX.fullmatch(value):
        bucket.add(value)


def _fetch_rippling_data(first, last):
    """
    Deprecated: Use RipplingClient.find_user_by_email instead.
    """
    return {}
