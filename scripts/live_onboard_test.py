#!/usr/bin/env python3
"""
Queue a manual onboarding request for headless scheduler processing.

This script replaces direct one-off onboarding execution. It writes a validated
manual override row into the scheduler queue (default `HOLD`, optional `READY`)
so unattended SERVUS can process it in the normal polling loop.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Allow running as `python3 scripts/live_onboard_test.py` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from servus.config import CONFIG
from servus.core.manual_override_enrichment import enrich_from_integrations
from servus.core.manual_override_queue import (
    HOLD_STATUS,
    ManualOverrideRequest,
    READY_STATUS,
    enqueue_request,
    ensure_override_csv,
)
from servus.models import UserProfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("manual_onboard_queue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Queue a manual onboarding request into the SERVUS override CSV."
    )
    parser.add_argument(
        "--csv-path",
        default=CONFIG.get("ONBOARDING_OVERRIDE_CSV", "servus_state/manual_onboarding_overrides.csv"),
        help="Path to manual override CSV queue",
    )
    parser.add_argument(
        "--profile-json",
        help="Optional JSON profile path. Supports old one-off keys (first,last,email,dept,type,manager) and UserProfile keys.",
    )
    parser.add_argument("--request-id", help="Unique request id. Auto-generated if omitted.")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument("--work-email")
    parser.add_argument("--department")
    parser.add_argument("--employment-type")
    parser.add_argument("--start-date", help="YYYY-MM-DD recommended")
    parser.add_argument("--personal-email")
    parser.add_argument("--title")
    parser.add_argument("--manager-email")
    parser.add_argument("--location", default="US")
    parser.add_argument("--confirmation-source-a")
    parser.add_argument("--confirmation-source-b")
    parser.add_argument(
        "--rippling-worker-id",
        help="Shortcut for confirmation source A. Expands to rippling:worker_id:<id>.",
    )
    parser.add_argument(
        "--freshservice-ticket-id",
        help="Shortcut for confirmation source B. Expands to freshservice:ticket_id:<id>. Accepts 140, INC-140, or ticket URL.",
    )
    parser.add_argument("--reason", default="")
    parser.add_argument(
        "--skip-integration-lookup",
        action="store_true",
        help="Disable Rippling/Okta auto-enrichment from work email.",
    )
    parser.add_argument(
        "--allow-update",
        action="store_true",
        help="Update existing request_id row instead of failing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print request without writing CSV",
    )
    parser.add_argument(
        "--ready",
        action="store_true",
        help="Queue request as READY (default queue status is HOLD).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Deprecated. Direct live execution is no longer supported by this script.",
    )
    return parser.parse_args()


def build_user_profile(args: argparse.Namespace) -> Tuple[UserProfile, List[str]]:
    profile_data: Dict[str, Any] = {}
    if args.profile_json:
        profile_data = load_profile_json(args.profile_json)

    kwargs = {
        "first_name": args.first_name or profile_data.get("first_name"),
        "last_name": args.last_name or profile_data.get("last_name"),
        "work_email": args.work_email or profile_data.get("work_email"),
        "department": args.department or profile_data.get("department"),
        "employment_type": args.employment_type or profile_data.get("employment_type"),
        "start_date": args.start_date or profile_data.get("start_date"),
        "personal_email": args.personal_email or profile_data.get("personal_email"),
        "title": args.title or profile_data.get("title"),
        "manager_email": args.manager_email or profile_data.get("manager_email"),
        "location": args.location or profile_data.get("location") or "US",
    }

    enrichment_sources = []
    if kwargs.get("work_email") and not args.skip_integration_lookup:
        enrichment = enrich_from_integrations(str(kwargs["work_email"]))
        for key, value in enrichment.profile_defaults.items():
            if not kwargs.get(key):
                kwargs[key] = value
        enrichment_sources = enrichment.confirmation_sources
        if enrichment.evidence:
            logger.info(
                "Integration enrichment for %s: %s",
                kwargs["work_email"],
                ", ".join(enrichment.evidence),
            )

    missing = [key for key in ["first_name", "last_name", "work_email", "department", "employment_type", "start_date"] if not kwargs.get(key)]
    if missing:
        raise ValueError(
            "Missing required profile fields after integration lookup: "
            f"{', '.join(missing)}. "
            "Provide values explicitly or verify Rippling/Okta connectivity."
        )

    return UserProfile(**kwargs), enrichment_sources


def load_profile_json(path: str) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile JSON must be an object")

    return {
        "first_name": payload.get("first_name") or payload.get("first"),
        "last_name": payload.get("last_name") or payload.get("last"),
        "work_email": payload.get("work_email") or payload.get("email"),
        "department": payload.get("department") or payload.get("dept"),
        "employment_type": payload.get("employment_type") or payload.get("type"),
        "start_date": payload.get("start_date"),
        "personal_email": payload.get("personal_email"),
        "title": payload.get("title"),
        "manager_email": payload.get("manager_email") or payload.get("manager"),
        "location": payload.get("location") or "US",
    }


def generate_request_id(work_email: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    local = work_email.split("@", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", local).strip("-") or "manual"
    return f"REQ-{timestamp}-{slug}"


def main() -> int:
    args = parse_args()
    if args.live:
        logger.error(
            "--live is deprecated for safety. This script only queues requests for headless scheduler execution."
        )
        return 2

    try:
        user, auto_confirmation_sources = build_user_profile(args)
        request_id = args.request_id or generate_request_id(str(user.work_email))
        confirmation_sources = _resolve_confirmation_sources(args, auto_confirmation_sources)
        request = ManualOverrideRequest(
            request_id=request_id,
            user_profile=user,
            confirmation_source_a=confirmation_sources[0],
            confirmation_source_b=confirmation_sources[1],
            reason=args.reason.strip() or None,
        )

        if args.dry_run:
            logger.info("Dry-run validation passed.")
            enqueue_status = READY_STATUS if args.ready else HOLD_STATUS
            logger.info(
                "Would enqueue request_id=%s email=%s status=%s csv=%s",
                request_id,
                user.work_email,
                enqueue_status,
                args.csv_path,
            )
            return 0

        ensure_override_csv(args.csv_path)
        enqueue_status = READY_STATUS if args.ready else HOLD_STATUS
        action = enqueue_request(
            args.csv_path,
            request,
            allow_update=args.allow_update,
            status=enqueue_status,
        )
        logger.info(
            "Queued manual onboarding request (%s): request_id=%s email=%s status=%s csv=%s",
            action,
            request_id,
            user.work_email,
            enqueue_status,
            args.csv_path,
        )
        if enqueue_status == READY_STATUS:
            logger.info("Scheduler will pick this up on the next polling cycle.")
        else:
            logger.info("Request is HOLD. Set status=READY (or re-run with --ready --allow-update) when approved.")
        return 0
    except Exception as exc:
        logger.error("Failed to queue manual onboarding request: %s", exc)
        return 1


def _resolve_confirmation_sources(
    args: argparse.Namespace,
    auto_sources: List[str],
) -> List[str]:
    requested = []
    if args.confirmation_source_a:
        requested.append(args.confirmation_source_a.strip())
    if args.confirmation_source_b:
        requested.append(args.confirmation_source_b.strip())

    requested.extend(_shortcut_confirmation_sources(args))

    for source in auto_sources:
        if source:
            requested.append(source)

    deduped = []
    seen = set()
    for source in requested:
        normalized = source.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)

    if len(deduped) < 2:
        raise ValueError(
            "Two confirmation sources are required. "
            "Provide --confirmation-source-a/--confirmation-source-b or ensure Rippling+Okta lookup succeeds."
        )

    return deduped[:2]


def _shortcut_confirmation_sources(args: argparse.Namespace) -> List[str]:
    sources: List[str] = []

    worker_id = _normalize_rippling_worker_id(args.rippling_worker_id)
    if worker_id:
        sources.append(f"rippling:worker_id:{worker_id}")

    ticket_id = _normalize_freshservice_ticket_id(args.freshservice_ticket_id)
    if ticket_id:
        sources.append(f"freshservice:ticket_id:{ticket_id}")

    return sources


def _normalize_rippling_worker_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""

    lowered = value.lower()
    prefix = "rippling:worker_id:"
    if lowered.startswith(prefix):
        return value[len(prefix):].strip()

    short_prefix = "worker_id:"
    if lowered.startswith(short_prefix):
        return value[len(short_prefix):].strip()

    return value


def _normalize_freshservice_ticket_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""

    lowered = value.lower()
    prefix = "freshservice:ticket_id:"
    if lowered.startswith(prefix):
        value = value[len(prefix):].strip()
        lowered = value.lower()

    short_prefix = "ticket_id:"
    if lowered.startswith(short_prefix):
        value = value[len(short_prefix):].strip()

    url_match = re.search(r"/tickets/(\d+)", value, flags=re.IGNORECASE)
    if url_match:
        return url_match.group(1)

    inc_match = re.match(r"(?i)^inc[-_ ]?(\d+)$", value)
    if inc_match:
        return inc_match.group(1)

    return value


if __name__ == "__main__":
    raise SystemExit(main())
