import requests
import logging
from servus.config import CONFIG

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

    def create_user(self, first, last, email):
        """
        Creates a new user in Brivo.
        """
        if not self.token and not self.login():
            return False

        existing = self.find_user(email)
        if existing:
            logger.info(f"ℹ️  Brivo User already exists: {existing.get('id')}")
            return True

        url = f"{self.base_url}/users"
        headers = {
            "api-key": self.api_key,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "firstName": first,
            "lastName": last,
            "email": email,
            "externalId": email
        }

        try:
            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code in [200, 201]:
                logger.info(f"✅ Created Brivo User: {first} {last}")
                return True
            else:
                logger.error(f"❌ Failed to create Brivo user: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Brivo API Error: {e}")
            return False

# --- WORKFLOW ACTIONS ---

def provision_access(context):
    user = context.get("user_profile")
    if not user: return False
    
    client = BrivoClient()
    return client.create_user(user.first_name, user.last_name, user.work_email)

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
