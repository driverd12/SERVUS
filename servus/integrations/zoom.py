import logging
import requests
from servus.config import CONFIG

logger = logging.getLogger("servus.zoom")

class ZoomClient:
    def __init__(self):
        self.account_id = CONFIG.get("ZOOM_ACCOUNT_ID")
        self.client_id = CONFIG.get("ZOOM_CLIENT_ID")
        self.client_secret = CONFIG.get("ZOOM_CLIENT_SECRET")
        self.base_url = "https://api.zoom.us/v2"
        self._token = None

    def _get_token(self):
        if self._token: return self._token
        
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}"
        try:
            resp = requests.post(url, auth=(self.client_id, self.client_secret))
            if resp.status_code == 200:
                self._token = resp.json().get("access_token")
                return self._token
        except Exception as e:
            logger.error(f"❌ Zoom Auth Error: {e}")
        return None

    def _request(self, method, endpoint, data=None):
        token = self._get_token()
        if not token: return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}{endpoint}"
        
        try:
            resp = requests.request(method, url, headers=headers, json=data)
            return resp
        except Exception as e:
            logger.error(f"❌ Zoom API Error: {e}")
            return None

    def assign_license(self, email, emp_type):
        """
        Assigns Basic (1) or Licensed (2) based on empType.
        """
        # 1 = Basic, 2 = Licensed
        license_type = 2 if "full-time" in emp_type.lower() else 1
        
        # First, find the user ID
        resp = self._request("GET", f"/users/{email}")
        if not resp or resp.status_code != 200:
            logger.warning(f"⚠️ Zoom: User {email} not found. (SCIM lag?)")
            return False
            
        user_id = resp.json().get("id")
        
        # Update settings
        payload = {"type": license_type}
        logger.info(f"🎥 Zoom: Setting license type {license_type} for {email}...")
        
        update_resp = self._request("PATCH", f"/users/{user_id}", data=payload)
        if update_resp and update_resp.status_code == 204:
            logger.info("✅ Zoom: License updated.")
            return True
        else:
            logger.error(f"❌ Zoom Update Failed: {update_resp.text if update_resp else 'No Resp'}")
            return False

    def add_to_group(self, email, group_name):
        # Implementation would require listing groups to find ID, then adding member
        # Placeholder for brevity
        pass

# --- Workflow Actions ---

def configure_user(context):
    user = context.get("user_profile")
    if not user: return False
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would configure Zoom license for {user.work_email}")
        return True

    client = ZoomClient()
    return client.assign_license(user.work_email, user.employment_type)
