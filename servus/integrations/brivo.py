import requests
import logging
import time
from servus.config import CONFIG
from servus.integrations import badge_queue

logger = logging.getLogger("servus.brivo")

class BrivoClient:
    def __init__(self):
        # API Client Deprecated - Only used for legacy/future reference if needed
        # We now use badge_queue for printing and assume manual/SCIM for management
        pass

    def login(self):
        logger.warning("⚠️ Brivo API Login is deprecated.")
        return False

    def find_user(self, email):
        logger.warning("⚠️ Brivo API User Search is deprecated.")
        return None

    def wait_for_user_scim(self, email):
        logger.warning("⚠️ Brivo SCIM Wait is deprecated.")
        return None

# --- WORKFLOW ACTIONS ---

def provision_access(context):
    """
    Triggers badge print job with user metadata.
    Note: Brivo user creation/binding is now MANUAL or handled by SCIM separately.
    This step only pushes the print job to the queue.
    """
    user = context.get("user_profile")
    if not user: return False
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would queue badge print job for {user.work_email}")
        return True

    logger.info("🖨️  Queueing Badge Print Job (Metadata Push)...")
    
    # Prepare data for the queue
    # We pass the profile data directly. The badge_queue module handles extraction.
    user_data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.work_email,
        "preferred_first_name": user.preferred_first_name,
        "profile_picture_url": user.profile_picture_url
    }
    
    badge_queue.send_print_job(user_data)
            
    return True

def suspend_user(context):
    """
    Suspends a user in Brivo (Revokes badge access).
    Note: Deprecated API usage. Should rely on SCIM.
    """
    logger.warning("🚫 Brivo: Suspend User is deprecated (Use SCIM).")
    return True