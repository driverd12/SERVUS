import logging
import requests
import yaml
import os
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
            logger.warning(f"Slack Lookup Failed for {email}: {data.get('error')}")
            return None
    except Exception as e:
        logger.error(f"Slack Connection Error: {e}")
        return None

def add_to_channels(context):
    """
    Adds the user to default and department-specific Slack channels.
    """
    user = context.get("user_profile")
    if not user: return False

    # 1. Get Slack User ID
    user_id = _lookup_user_by_email(user.email)
    if not user_id:
        logger.warning(f"Skipping channel add: Could not find Slack user for {user.email}. (SCIM sync delay?)")
        return False

    # 2. Load Channel Rules
    channels_file = os.path.join("servus", "data", "slack_channels.yaml")
    if not os.path.exists(channels_file):
        logger.error(f"Missing data file: {channels_file}")
        return False

    with open(channels_file, 'r') as f:
        config = yaml.safe_load(f)

    # 3. Determine Target Channels
    target_channels = set(config.get("global", [])) # Start with global
    
    # Normalize department to lowercase for matching
    dept_key = user.department.lower() if user.department else "unknown"
    
    # Add Department specific channels if defined
    if dept_key in config.get("departments", {}):
        target_channels.update(config["departments"][dept_key])
    
    logger.info(f"Adding {user.email} to {len(target_channels)} Slack channels...")

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
