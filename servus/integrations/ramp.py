import logging
import requests
from servus.config import CONFIG

logger = logging.getLogger("servus.ramp")

class RampClient:
    def __init__(self):
        self.api_key = CONFIG.get("RAMP_API_KEY") # Bearer token
        self.base_url = "https://api.ramp.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    def assign_spend_profile(self, email, department):
        """
        Assigns a spend profile based on department.
        """
        if not self.api_key:
            logger.warning("⚠️ Ramp API Key missing. Skipping.")
            return {"ok": True, "detail": "RAMP_API_KEY missing; skipped Ramp spend profile assignment."}

        # 1. Find User
        # Ramp API structure varies, assuming /users endpoint
        # This is a placeholder implementation based on typical patterns
        logger.info(f"💳 Ramp: Assigning spend profile for {email} ({department})...")
        
        # In a real implementation, we'd:
        # 1. GET /users?email={email} -> get user_id
        # 2. Determine profile_id based on department map
        # 3. PUT /users/{user_id} { "spend_profile_id": ... }
        
        return {
            "ok": True,
            "detail": f"Ramp spend profile placeholder completed for {email} (department={department}).",
        }

# --- Workflow Actions ---

def configure_user(context):
    user = context.get("user_profile")
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would configure Ramp spend profile for {user.work_email}")
        return {"ok": True, "detail": "Dry run: would configure Ramp spend profile."}

    client = RampClient()
    return client.assign_spend_profile(user.work_email, user.department)
