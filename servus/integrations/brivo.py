import requests
import logging
import time
from servus.config import CONFIG
from servus.integrations import badge_queue

logger = logging.getLogger("servus.brivo")

class BrivoClient:
    def __init__(self):
        self.api_key = CONFIG.get("BRIVO_API_KEY")
        self.username = CONFIG.get("BRIVO_USERNAME")
        self.password = CONFIG.get("BRIVO_PASSWORD")
        self.base_url = "https://api.brivo.com/v1/api"
        self.token = None

    def login(self):
        """
        Exchanges credentials for a Session Token.
        """
        if not self.api_key or not self.username:
            logger.error("❌ Brivo config missing.")
            return False

        url = f"{self.base_url}/login"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        data = {
            "username": self.username,
            "password": self.password
        }

        try:
            resp = requests.post(url, json=data, headers=headers)
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                logger.info("✅ Brivo Login Successful.")
                return True
            else:
                logger.error(f"❌ Brivo Login Failed {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Brivo Connection Error: {e}")
            return False

    def find_user(self, email):
        """
        Checks if user exists (to prevent duplicates).
        """
        if not self.token and not self.login():
            return None

        # Searching usually requires a filter query
        url = f"{self.base_url}/users?filter=email eq '{email}'"
        headers = {
            "api-key": self.api_key,
            "Authorization": f"Bearer {self.token}"
        }

        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                users = resp.json().get("data", [])
                if users:
                    return users[0] # Return the first match
            return None
        except Exception:
            return None

    def wait_for_user_scim(self, email):
        """
        Polls Brivo to wait for the user to be created by Okta SCIM.
        """
        logger.info(f"⏳ Brivo: Waiting for SCIM to create {email}...")
        
        start_time = time.time()
        timeout = 600 # 10 minutes
        
        while time.time() - start_time < timeout:
            user = self.find_user(email)
            if user:
                logger.info(f"✅ Brivo: User {email} found (SCIM Synced)!")
                return user
            time.sleep(30)
            
        logger.error(f"❌ Brivo: Timed out waiting for {email}")
        return None

# --- WORKFLOW ACTIONS ---

def provision_access(context):
    """
    Waits for Okta SCIM to create the user in Brivo, then triggers badge print.
    """
    user = context.get("user_profile")
    if not user: return False
    
    client = BrivoClient()
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would wait for Brivo SCIM sync for {user.work_email}")
        logger.info(f"[DRY-RUN] Would queue badge print job.")
        return True

    # 1. Wait for SCIM
    brivo_user = client.wait_for_user_scim(user.work_email)
    if not brivo_user:
        return False
        
    # 2. Trigger Print Job
    # We fetch the photo URL from Okta (or assume it flowed to Brivo if mapped)
    # For this implementation, we rely on the local agent to pull the photo 
    # OR we pass a URL if we have one. Okta API might be needed here to get the photo URL.
    
    # Placeholder for Photo URL logic
    photo_url = None 
    
    logger.info("🖨️  Queueing Badge Print Job...")
    badge_queue.send_print_job({
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.work_email,
        "photo_url": photo_url,
        "brivo_id": brivo_user.get("id")
    })
            
    return True

def suspend_user(context):
    """
    Suspends a user in Brivo (Revokes badge access).
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    client = BrivoClient()
    
    logger.info(f"🚫 Brivo: Suspending badge for {user_profile.work_email}...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would find Brivo user and set suspended=True")
        return True

    # 1. Login & Find
    if not client.login():
        return False
        
    brivo_user = client.find_user(user_profile.work_email)
    if not brivo_user:
        logger.warning(f"⚠️ Brivo user not found. Skipping suspension.")
        return False
        
    user_id = brivo_user.get("id")
    
    # 2. Suspend
    url = f"{client.base_url}/users/{user_id}"
    headers = {
        "api-key": client.api_key,
        "Authorization": f"Bearer {client.token}",
        "Content-Type": "application/json"
    }
    data = {"suspended": True}
    
    try:
        resp = requests.put(url, json=data, headers=headers)
        if resp.status_code in [200, 204]:
            logger.info(f"✅ Brivo User Suspended.")
            return True
        else:
            logger.error(f"❌ Brivo Suspend Failed: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Brivo Connection Error: {e}")
        return False