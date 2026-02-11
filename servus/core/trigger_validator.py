import logging
from servus.integrations.rippling import RipplingClient
from servus.integrations import freshservice

logger = logging.getLogger("servus.trigger_validator")

def validate_and_fetch_context():
    """
    Dual-Validation Logic:
    1. Poll Rippling for "Ready" users (Completed pre-reqs).
    2. Poll Freshservice for "New Hire" tickets.
    3. Match them.
    4. Return list of validated user profiles.
    """
    logger.info("🔒 Trigger Validator: Starting Dual-Validation Scan...")
    
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
    ticket_ids = freshservice.scan_for_onboarding_tickets(minutes_lookback=1440)
    freshservice_emails = set()
    
    # We need to peek at the tickets to get emails for matching
    # This is expensive if there are many tickets, but usually volume is low
    for tid in ticket_ids:
        user = freshservice.fetch_ticket_data(tid)
        if user and user.work_email:
            freshservice_emails.add(user.work_email.lower())

    # 3. Match & Validate
    validated_users = []
    
    for r_user in rippling_users:
        email = r_user.work_email.lower()
        if email in freshservice_emails:
            logger.info(f"✅ VALIDATED MATCH: {email}")
            logger.info(f"   - Rippling: Ready")
            logger.info(f"   - Freshservice: Ticket Exists")
            validated_users.append(r_user)
        else:
            logger.warning(f"⚠️  MISMATCH: {email} found in Rippling but NO Freshservice ticket found.")
            # Alert IT? (Log is the alert for now)
            
    return validated_users
