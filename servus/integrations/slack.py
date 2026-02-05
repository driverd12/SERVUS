import logging
import requests
import yaml
import os
import time
from servus.config import CONFIG

logger = logging.getLogger("servus.slack")

def _get_headers():
    token = CONFIG.get("SLACK_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def _lookup_user_by_email(email):
    """Finds the Slack User ID (e.g., U123456) from an email address."""
    url = "https://slack.com/api/users.lookupByEmail"
    try:
        r = requests.get(url, headers=_get_headers(), params={"email": email}, timeout=10)
        data = r.json()
        if data.get("ok"):
            return data["user"]["id"]
        else:
            # Don't log warning here, let the caller handle it (e.g. in wait loop)
            return None
    except Exception as e:
        logger.error(f"Slack Connection Error: {e}")
        return None

def add_to_channels(context):
    """
    Adds the user to default and department-specific Slack channels.
    Waits for user to exist (SCIM sync).
    """
    user = context.get("user_profile")
    if not user: return False

    # 1. Get Slack User ID with Wait Loop
    user_id = None
    email = user.email
    
    logger.info(f"⏳ Slack: Waiting for user {email} to exist...")
    
    start_time = time.time()
    timeout = 300 # 5 minutes
    
    while time.time() - start_time < timeout:
        user_id = _lookup_user_by_email(email)
        if user_id:
            logger.info(f"✅ Slack: User found ({user_id})")
            break
        
        if context.get("dry_run"):
             logger.info(f"[DRY-RUN] Would wait for Slack user {email}")
             user_id = "U_DRY_RUN"
             break
             
        time.sleep(30)
        
    if not user_id:
        logger.warning(f"Skipping channel add: Could not find Slack user for {email} after {timeout}s. (SCIM sync delay?)")
        return False

    # 2. Load Channel Rules
    channels_file = os.path.join("servus", "data", "slack_channels.yaml")
    if not os.path.exists(channels_file):
        logger.error(f"Missing data file: {channels_file}")
        return False

    with open(channels_file, 'r') as f:
        config = yaml.safe_load(f)

    # 3. Determine Target Channels
    target_channels = set()
    emp_type = user.employment_type.lower()
    
    # A. Employee Type Logic
    if "supplier" in emp_type:
        logger.info("   ℹ️ Supplier detected - skipping default channels.")
        # Suppliers get NO default channels, only explicit department ones if allowed
    else:
        # Everyone else gets Global channels
        target_channels.update(config.get("global", []))
        
        # Specific Role Channels
        if "full-time" in emp_type:
            # Add FTE specific channels if any (e.g. #all-hands is usually in global, but if split:)
            target_channels.add("all-hands") 
        elif "contractor" in emp_type or "1099" in emp_type:
            target_channels.add("contractors")
        elif "intern" in emp_type or "temporary" in emp_type:
            target_channels.add("interns")

    # B. Department Logic
    # Normalize department to lowercase for matching
    dept_key = user.department.lower() if user.department else "unknown"
    
    # Add Department specific channels if defined
    # Note: Suppliers might need to be excluded here too depending on policy, 
    # but usually if they are in "Engineering" they need "engineering-chat".
    if dept_key in config.get("departments", {}):
        target_channels.update(config["departments"][dept_key])
    
    logger.info(f"Adding {user.email} to {len(target_channels)} Slack channels...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would add to: {target_channels}")
        return True

    # 4. Invite User
    url = "https://slack.com/api/conversations.invite"
    success_count = 0
    
    for channel_id in target_channels:
        if not channel_id: continue # Skip empty
        
        payload = {"channel": channel_id, "users": user_id}
        r = requests.post(url, headers=_get_headers(), json=payload)
        resp = r.json()
        
        if resp.get("ok"):
            logger.info(f" - Added to {channel_id}")
            success_count += 1
        elif resp.get("error") == "already_in_channel":
            # This is fine, just means they are already there
            success_count += 1
        else:
            logger.error(f" - Failed to add to {channel_id}: {resp.get('error')}")

    return success_count > 0

def deactivate_user(context):
    """
    Deactivates a user in Slack using the SCIM API.
    """
    user = context.get("user_profile")
    if not user: return False
    email = user.work_email

    logger.info(f"🚫 Slack: Deactivating {email}...")

    # 1. Find User ID
    user_id = _lookup_user_by_email(email)
    if not user_id:
        logger.warning(f"⚠️ Slack: User {email} not found. Skipping deactivation.")
        return False

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would deactivate Slack user {user_id}")
        return True

    # 2. Deactivate via SCIM API (DELETE /Users/{id})
    # Note: This requires an Admin token with SCIM scopes or a Grid Admin token.
    url = f"https://api.slack.com/scim/v1/Users/{user_id}"
    headers = _get_headers()
    
    try:
        resp = requests.delete(url, headers=headers)
        if resp.status_code == 200 or resp.status_code == 204:
            logger.info(f"✅ Slack: User {email} deactivated.")
            return True
        else:
            logger.error(f"❌ Slack Deactivation Failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Slack Connection Error: {e}")
        return False
