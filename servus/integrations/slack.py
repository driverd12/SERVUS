import logging
import requests
import yaml
import os
import time
from servus.config import CONFIG

logger = logging.getLogger("servus.slack")
CHANNELS_FILE = os.path.join("servus", "data", "slack_channels.yaml")

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


def _normalize_list(raw_values):
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    if not isinstance(raw_values, list):
        return []

    values = []
    for value in raw_values:
        normalized = str(value or "").strip()
        if normalized:
            values.append(normalized)
    return values


def _load_channel_policy():
    if not os.path.exists(CHANNELS_FILE):
        logger.warning("Missing data file: %s. Slack channel assignment skipped.", CHANNELS_FILE)
        return {"global": [], "departments": {}, "employment_type": {}}

    with open(CHANNELS_FILE, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    global_channels = _normalize_list(config.get("global"))
    dept_channels = {}
    for key, value in (config.get("departments") or {}).items():
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        dept_channels[normalized_key] = _normalize_list(value)

    employment_type_channels = {}
    for key, value in (config.get("employment_type") or {}).items():
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        employment_type_channels[normalized_key] = _normalize_list(value)

    return {
        "global": global_channels,
        "departments": dept_channels,
        "employment_type": employment_type_channels,
    }


def _employment_key(employment_type):
    emp_type = str(employment_type or "").strip().lower()
    if "supplier" in emp_type:
        return "supplier"
    if any(token in emp_type for token in ("intern", "temporary")):
        return "intern"
    if any(token in emp_type for token in ("contractor", "1099")):
        return "contractor"
    if "full-time" in emp_type:
        return "full_time"
    return "other"


def _target_channels_for_user(user, policy):
    target_channels = set()

    # Global channel assignment applies to all non-supplier users by default.
    if _employment_key(user.employment_type) != "supplier":
        target_channels.update(policy.get("global", []))

    employment_type_channels = policy.get("employment_type", {})
    target_channels.update(employment_type_channels.get(_employment_key(user.employment_type), []))

    dept_key = str(user.department or "").strip().lower()
    department_channels = policy.get("departments", {})
    target_channels.update(department_channels.get(dept_key, []))

    return sorted(ch for ch in target_channels if ch)

def add_to_channels(context):
    """
    Adds the user to default and department-specific Slack channels.
    Waits for user to exist (SCIM sync).
    """
    user = context.get("user_profile")
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    policy = _load_channel_policy()
    target_channels = _target_channels_for_user(user, policy)
    if not target_channels:
        return {"ok": True, "detail": "No Slack channels matched policy; skipped."}

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would add {user.work_email} to channels: {target_channels}")
        return {"ok": True, "detail": f"Dry run: would add to channels {target_channels}."}

    if not CONFIG.get("SLACK_TOKEN"):
        logger.warning("⚠️ Slack token missing. Skipping Slack channel assignment.")
        return {"ok": True, "detail": "SLACK_TOKEN missing; skipped Slack channel assignment."}

    # 1. Get Slack User ID with Wait Loop
    user_id = None
    email = user.work_email
    
    logger.info(f"⏳ Slack: Waiting for user {email} to exist...")
    
    start_time = time.time()
    timeout = 300 # 5 minutes
    
    while time.time() - start_time < timeout:
        user_id = _lookup_user_by_email(email)
        if user_id:
            logger.info(f"✅ Slack: User found ({user_id})")
            break
        
        time.sleep(30)
        
    if not user_id:
        logger.warning(
            f"Skipping channel add: Could not find Slack user for {email} after {timeout}s. (SCIM sync delay?)"
        )
        return {
            "ok": True,
            "detail": f"Slack user not found after {timeout}s; channel assignment skipped (SCIM lag).",
        }

    logger.info(f"Adding {user.work_email} to {len(target_channels)} Slack channels...")

    # 4. Invite User
    url = "https://slack.com/api/conversations.invite"
    added_count = 0
    already_in_channel_count = 0
    failed_channels = []
    
    for channel_id in target_channels:
        if not channel_id: continue # Skip empty
        
        payload = {"channel": channel_id, "users": user_id}
        r = requests.post(url, headers=_get_headers(), json=payload, timeout=10)
        resp = r.json()
        
        if resp.get("ok"):
            logger.info(f" - Added to {channel_id}")
            added_count += 1
        elif resp.get("error") == "already_in_channel":
            # This is fine, just means they are already there
            logger.info(f" - Already in {channel_id}")
            already_in_channel_count += 1
        else:
            error_code = resp.get("error") or "unknown_error"
            logger.error(f" - Failed to add to {channel_id}: {error_code}")
            failed_channels.append(f"{channel_id}:{error_code}")

    ok = len(failed_channels) == 0
    detail = (
        f"target_channels={len(target_channels)}, added={added_count}, "
        f"already_in_channel={already_in_channel_count}, failed={len(failed_channels)}"
    )
    if failed_channels:
        detail += f", failed_channels={failed_channels}"
    return {"ok": ok, "detail": detail}

def deactivate_user(context):
    """
    Deactivates a user in Slack using the SCIM API.
    """
    user = context.get("user_profile")
    if not user: return False
    email = user.work_email

    logger.info(f"🚫 Slack: Deactivating {email}...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would deactivate Slack user matching {email}")
        return True

    # 1. Find User ID
    user_id = _lookup_user_by_email(email)
    
    if not user_id:
        # If not found, it might be due to auth error or actually not found.
        # We need to be careful not to return True on Auth Error.
        # _lookup_user_by_email returns None on error.
        # We should verify if the token is valid first or handle error in lookup.
        
        # Let's try a simple auth test to distinguish
        try:
            auth_test = requests.post("https://slack.com/api/auth.test", headers=_get_headers())
            if not auth_test.json().get("ok"):
                logger.error(f"❌ Slack Auth Failed: {auth_test.json().get('error')}")
                return False
        except:
            pass

        logger.warning(f"⚠️ Slack: User {email} not found (May already be deactivated).")
        return True 

    # Check if user is already deleted
    try:
        info_url = f"https://slack.com/api/users.info?user={user_id}"
        r = requests.get(info_url, headers=_get_headers())
        info = r.json()
        if info.get("ok") and info.get("user", {}).get("deleted"):
            logger.info(f"✅ Slack: User {email} is ALREADY deactivated.")
            return True
    except Exception:
        pass 

    # 2. Deactivate via SCIM API (DELETE /Users/{id})
    # Note: This requires an Admin token with SCIM scopes or a Grid Admin token.
    # If SCIM is not enabled, we might need to use users.admin.setInactive (Legacy)
    url = f"https://api.slack.com/scim/v1/Users/{user_id}"
    headers = _get_headers()
    
    try:
        resp = requests.delete(url, headers=headers)
        if resp.status_code == 200 or resp.status_code == 204:
            logger.info(f"✅ Slack: User {email} deactivated (SCIM).")
            return True
        else:
            # Fallback to Legacy Admin API if SCIM fails (e.g. 404/403/501)
            logger.warning(f"⚠️ Slack SCIM Deactivation failed ({resp.status_code}). Trying Legacy API...")
            
            legacy_url = "https://slack.com/api/users.admin.setInactive"
            legacy_resp = requests.post(legacy_url, headers=headers, data={"user": user_id})
            legacy_data = legacy_resp.json()
            
            if legacy_data.get("ok"):
                logger.info(f"✅ Slack: User {email} deactivated (Legacy API).")
                return True
            else:
                logger.error(f"❌ Slack Deactivation Failed: {legacy_data.get('error')}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Slack Connection Error: {e}")
        return False
