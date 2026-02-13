import logging
from dataclasses import dataclass
from typing import List

from servus.integrations.rippling import RipplingClient
from servus.integrations import freshservice

logger = logging.getLogger("servus.trigger_validator")


@dataclass
class ValidatedTrigger:
    user_profile: object
    confirmation_source_a: str
    confirmation_source_b: str


def validate_and_fetch_context():
    """
    Backward-compatible onboarding helper that returns only user profiles.
    """
    return [match.user_profile for match in validate_and_fetch_onboarding_context()]


def validate_and_fetch_onboarding_context(minutes_lookback=1440) -> List[ValidatedTrigger]:
    """
    Dual-Validation Logic:
    1. Poll Rippling for "Ready" users (Completed pre-reqs).
    2. Poll Freshservice for "New Hire" tickets.
    3. Match them.
    4. Return list of validated user profiles.
    """
    logger.info("🔒 Trigger Validator: Starting Onboarding Dual-Validation Scan...")
    
    # 1. Rippling Scan
    rippling = RipplingClient()
    # Assuming get_new_hires returns users starting TODAY
    # In a real "completed pre-reqs" scenario, we might query a different status field
    # But for now, we stick to the start_date logic as the proxy for "Ready"
    rippling_users = rippling.get_new_hires() 
    
    if not rippling_users:
        logger.info("   No Rippling users found for today.")
        return []

    # 2. Freshservice Scan
    # We look back 24 hours to be safe, or just check open tickets
    ticket_ids = freshservice.scan_for_onboarding_tickets(minutes_lookback=minutes_lookback)
    freshservice_ticket_by_email = freshservice.map_ticket_ids_by_email(ticket_ids)

    # 3. Match & Validate
    validated_matches: List[ValidatedTrigger] = []
    
    for r_user in rippling_users:
        email = r_user.work_email.lower()
        ticket_id = freshservice_ticket_by_email.get(email)
        if ticket_id:
            logger.info(f"✅ VALIDATED MATCH: {email}")
            logger.info(f"   - Rippling: Ready")
            logger.info(f"   - Freshservice: Ticket #{ticket_id} Exists")
            validated_matches.append(
                ValidatedTrigger(
                    user_profile=r_user,
                    confirmation_source_a=f"rippling:onboarding:{email}",
                    confirmation_source_b=f"freshservice:ticket_id:{ticket_id}",
                )
            )
        else:
            logger.warning(f"⚠️  MISMATCH: {email} found in Rippling but NO Freshservice ticket found.")
            # Alert IT? (Log is the alert for now)
            
    return validated_matches


def validate_and_fetch_offboarding_context(minutes_lookback=1440) -> List[ValidatedTrigger]:
    """
    Dual-confirmed departures:
    1. Rippling departure feed for today.
    2. Freshservice offboarding ticket feed.
    """
    logger.info("🔒 Trigger Validator: Starting Offboarding Dual-Validation Scan...")

    rippling = RipplingClient()
    departures = rippling.get_departures()
    if not departures:
        logger.info("   No Rippling departures found for today.")
        return []

    ticket_ids = freshservice.scan_for_offboarding_tickets(minutes_lookback=minutes_lookback)
    freshservice_ticket_by_email = freshservice.map_ticket_ids_by_email(ticket_ids)

    validated_matches: List[ValidatedTrigger] = []
    for departing_user in departures:
        email = (departing_user.work_email or "").strip().lower()
        if not email:
            continue

        ticket_id = freshservice_ticket_by_email.get(email)
        if ticket_id:
            logger.info("✅ VALIDATED DEPARTURE: %s", email)
            logger.info("   - Rippling: Departure detected")
            logger.info("   - Freshservice: Ticket #%s Exists", ticket_id)
            validated_matches.append(
                ValidatedTrigger(
                    user_profile=departing_user,
                    confirmation_source_a=f"rippling:offboarding:{email}",
                    confirmation_source_b=f"freshservice:ticket_id:{ticket_id}",
                )
            )
        else:
            logger.warning(
                "⚠️  MISMATCH: %s found in Rippling departures but no Freshservice offboarding ticket found.",
                email,
            )

    return validated_matches
