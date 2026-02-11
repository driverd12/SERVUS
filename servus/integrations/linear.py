import logging
import requests
from servus.config import CONFIG

logger = logging.getLogger("servus.linear")

class LinearClient:
    def __init__(self):
        self.api_key = CONFIG.get("LINEAR_API_KEY")
        self.api_url = "https://api.linear.app/graphql"
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }

    def _query(self, query, variables=None):
        if not self.api_key:
            logger.error("❌ Linear API Key missing.")
            return None
            
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"❌ Linear API Error: {e}")
            return None

    def invite_user(self, email, role="guest"):
        """
        Invites a user to the workspace.
        """
        mutation = """
        mutation UserInvite($email: String!, $role: UserRole!) {
            userInvite(input: { email: $email, role: $role }) {
                success
                user { id email }
            }
        }
        """
        variables = {"email": email, "role": role.upper()} # ADMIN, GUEST, MEMBER
        
        logger.info(f"🚀 Linear: Inviting {email} as {role}...")
        result = self._query(mutation, variables)
        
        if result and result.get("data", {}).get("userInvite", {}).get("success"):
            logger.info(f"✅ Linear: Invited {email}")
            return True
        else:
            # Check if already exists
            errors = result.get("errors", []) if result else []
            if any("already exists" in str(e) for e in errors):
                logger.info(f"✅ Linear: User {email} already exists.")
                return True
            
            logger.error(f"❌ Linear Invite Failed: {errors}")
            return False

    def verify_user_deprovisioned(self, email):
        """
        Checks if a user is active. If found and active, returns False (Failure).
        If not found or suspended, returns True (Success).
        """
        query = """
        query Users($email: String) {
            users(filter: { email: { eq: $email } }) {
                nodes {
                    id
                    email
                    active
                }
            }
        }
        """
        variables = {"email": email}
        
        logger.info(f"🔍 Linear: Verifying deprovisioning for {email}...")
        result = self._query(query, variables)
        
        if not result:
            return False # API failure
            
        users = result.get("data", {}).get("users", {}).get("nodes", [])
        
        if not users:
            logger.info(f"✅ Linear: User {email} not found (Deprovisioned).")
            return True
            
        user = users[0]
        if user.get("active"):
            logger.warning(f"⚠️  Linear: User {email} is still ACTIVE.")
            return False
        else:
            logger.info(f"✅ Linear: User {email} found but SUSPENDED.")
            return True

# --- Workflow Actions ---

def provision_user(context):
    user = context.get("user_profile")
    if not user: return False
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would invite {user.work_email} to Linear.")
        return True

    client = LinearClient()
    # Logic to determine role based on empType?
    # Defaulting to MEMBER for FTE, GUEST for others
    role = "MEMBER" if "full-time" in user.employment_type.lower() else "GUEST"
    return client.invite_user(user.work_email, role)

def verify_deprovisioned(context):
    user = context.get("user_profile")
    if not user: return False
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would verify {user.work_email} is removed from Linear.")
        return True

    client = LinearClient()
    return client.verify_user_deprovisioned(user.work_email)
