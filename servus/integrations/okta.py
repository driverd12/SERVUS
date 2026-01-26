import requests
import logging
import time
import json
from servus.config import CONFIG

logger = logging.getLogger("servus.okta")

class OktaClient:
    def __init__(self):
        self.domain = CONFIG.get("OKTA_DOMAIN")
        self.token = CONFIG.get("OKTA_TOKEN")
        self.base_url = f"https://{self.domain}/api/v1"
        self.headers = {
            "Authorization": f"SSWS {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_user(self, email):
        """
        Fetches a user by email. Returns the user object or None.
        """
        if not self.domain or not self.token:
            logger.error("❌ Okta config missing (DOMAIN or TOKEN).")
            return None

        # Okta allows searching by profile.email
        url = f"{self.base_url}/users?q={email}&limit=1"
        
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                users = resp.json()
                if users:
                    return users[0]
            return None
        except Exception as e:
            logger.error(f"❌ Okta API Error: {e}")
            return None

    def add_user_to_group(self, user_id, group_id):
        """
        Adds a user to a specific Okta group.
        """
        url = f"{self.base_url}/groups/{group_id}/users/{user_id}"
        try:
            resp = requests.put(url, headers=self.headers)
            if resp.status_code == 204:
                logger.info(f"✅ Added user {user_id} to group {group_id}")
                return True
            else:
                logger.error(f"❌ Failed to add to group {group_id}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Group Add Error: {e}")
            return False

# --- WORKFLOW ACTIONS ---

def wait_for_user(context):
    """
    POLLING LOOP: Waits for the user to sync from Rippling to Okta.
    Retries every 30 seconds for up to 10 minutes.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    target_email = user_profile.work_email
    client = OktaClient()
    
    max_retries = 20  # 10 minutes total
    interval = 30     # 30 seconds wait
    
    logger.info(f"⏳ Polling Okta: Waiting for {target_email} to arrive from Rippling...")
    
    if context.get("dry_run"):
        logger.info("[DRY-RUN] Would poll Okta API until user is found.")
        return True

    for attempt in range(1, max_retries + 1):
        okta_user = client.get_user(target_email)
        
        if okta_user:
            user_id = okta_user.get("id")
            status = okta_user.get("status")
            logger.info(f"✅ User found in Okta! (ID: {user_id} | Status: {status})")
            
            # Store Okta ID in context for later steps if needed
            context["okta_user_id"] = user_id
            return True
        
        logger.info(f"   ... Attempt {attempt}/{max_retries}: User not found yet. Waiting {interval}s.")
        time.sleep(interval)

    logger.error(f"❌ TIMEOUT: User {target_email} never appeared in Okta after 10 minutes.")
    return False

def assign_custom_groups(context):
    """
    Assigns specific groups based on attributes (e.g. Contractors).
    Useful for things SCIM rules might miss or for 'Day 1' logic.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    # We need the Okta User ID (should be in context from the 'wait' step)
    # If not, we fetch it quickly.
    client = OktaClient()
    user_id = context.get("okta_user_id")
    
    if not user_id:
        okta_user = client.get_user(user_profile.work_email)
        if okta_user:
            user_id = okta_user.get("id")
        else:
            logger.error("❌ Cannot assign groups: User not found in Okta.")
            return False

    # Example Logic: Assign "Contractors" group if type matches
    # You would put your REAL Group IDs in your .env or config
    contractor_group_id = CONFIG.get("OKTA_GROUP_CONTRACTORS") 
    
    if user_profile.employment_type == "Contractor" and contractor_group_id:
        logger.info("Detected Contractor: Assigning to Okta Contractor Group...")
        if context.get("dry_run"):
            logger.info(f"[DRY-RUN] Would add user {user_id} to group {contractor_group_id}")
        else:
            client.add_user_to_group(user_id, contractor_group_id)

    return True
