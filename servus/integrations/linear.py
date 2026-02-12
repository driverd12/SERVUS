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
            payload = response.json()
            if response.status_code >= 400:
                logger.error(
                    "❌ Linear HTTP Error: status=%s payload=%s",
                    response.status_code,
                    payload,
                )
            return payload
        except Exception as e:
            logger.error(f"❌ Linear API Error: {e}")
            return None

    def invite_user(self, email, role="guest"):
        """
        Invites a user to the workspace.
        """
        mutation = """
        mutation OrganizationInviteCreate($input: OrganizationInviteCreateInput!) {
            organizationInviteCreate(input: $input) {
                success
                organizationInvite {
                    id
                    email
                    role
                    acceptedAt
                }
            }
        }
        """
        normalized_role = _normalize_invite_role(role)
        variables = {
            "input": {
                "email": email,
                "role": normalized_role,  # owner/admin/guest/user/app
            }
        }
        
        logger.info(f"🚀 Linear: Inviting {email} as {normalized_role}...")
        result = self._query(mutation, variables)
        
        payload = (
            (result or {})
            .get("data", {})
            .get("organizationInviteCreate", {})
        )
        if payload.get("success"):
            logger.info(f"✅ Linear: Invited {email}")
            return {"ok": True, "detail": f"Invited {email} to Linear as {normalized_role}."}

        errors = result.get("errors", []) if result else []
        if _is_already_exists_error(errors):
            logger.info(f"✅ Linear: User {email} already exists or is already invited.")
            return {"ok": True, "detail": f"Linear user {email} already exists/invited; invite skipped."}

        logger.error(f"❌ Linear Invite Failed: {errors}")
        return {"ok": False, "detail": f"Linear invite failed: {_format_errors(errors)}"}

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
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would invite {user.work_email} to Linear.")
        return {"ok": True, "detail": "Dry run: would invite user to Linear."}

    client = LinearClient()
    if not client.api_key:
        return {"ok": True, "detail": "LINEAR_API_KEY missing; skipped Linear invite."}
    # Logic to determine role based on empType?
    # Defaulting to "user" for FTE, "guest" for others.
    role = "user" if "full-time" in user.employment_type.lower() else "guest"
    return client.invite_user(user.work_email, role)

def verify_deprovisioned(context):
    user = context.get("user_profile")
    if not user: return False
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would verify {user.work_email} is removed from Linear.")
        return True

    client = LinearClient()
    return client.verify_user_deprovisioned(user.work_email)


def _is_already_exists_error(errors):
    for entry in errors or []:
        text = str(entry).lower()
        if any(
            phrase in text
            for phrase in [
                "already exists",
                "already invited",
                "already a member",
                "duplicate",
            ]
        ):
            return True
    return False


def _format_errors(errors):
    if not errors:
        return "unknown error"
    first = errors[0]
    if isinstance(first, dict):
        message = first.get("message")
        if message:
            return str(message)
    return str(first)


def _normalize_invite_role(role):
    normalized = str(role or "").strip().lower()
    mapping = {
        "member": "user",
        "user": "user",
        "guest": "guest",
        "admin": "admin",
        "owner": "owner",
        "app": "app",
    }
    return mapping.get(normalized, "guest")
