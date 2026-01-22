import os
import subprocess
import logging
from servus.config import CONFIG

logger = logging.getLogger("servus.gam")

def _run_gam(args):
    """Internal helper to run GAM commands securely."""
    gam_path = CONFIG.get("GAM_PATH", "gam") # Default to 'gam' if not set
    
    # Ensure full path is valid
    if not os.path.exists(gam_path) and gam_path != "gam":
        logger.error(f"GAM binary not found at {gam_path}")
        return False

    cmd = [gam_path] + args
    
    try:
        # We capture output to keep logs clean, but log errors
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return True
        else:
            logger.error(f"GAM Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"GAM Execution Failed: {str(e)}")
        return False

def move_user_ou(context):
    """
    Moves the user to the correct Google OU based on their FTE/Contractor status.
    Expected context: user_profile (with email, type)
    """
    user = context.get("user_profile")
    if not user: return False

    email = user.email
    
    # Determine Target OU based on User Type
    # You can customize these paths in your .env or Config if preferred
    if user.user_type == "CON":
        target_ou = "/New Users - Contractors"
    elif user.user_type == "INT":
        target_ou = "/New Users - Interns"
    else:
        target_ou = "/New Users - FTE"

    logger.info(f"Moving {email} to Google OU: {target_ou}")
    
    # GAM Command: gam update user <email> org <ou>
    return _run_gam(["update", "user", email, "org", target_ou])

def add_to_groups(context):
    """
    Adds user to standard distribution lists.
    """
    user = context.get("user_profile")
    if not user: return False

    email = user.email
    groups_to_add = []

    # Logic for standard groups
    if user.user_type == "FTE":
        groups_to_add.append("team@boom.aero")
    elif user.user_type == "CON":
        groups_to_add.append("contractors@boom.aero")
    
    # Add logic for Department groups here if needed (e.g. engineering@)
    
    success = True
    for group in groups_to_add:
        logger.info(f"Adding {email} to Google Group: {group}")
        # GAM Command: gam update group <group> add member <email>
        if not _run_gam(["update", "group", group, "add", "member", email]):
            success = False
            
    return success

def ensure_alias(context):
    """
    Ensures the user has their old email as an alias (useful for re-hires/conversions).
    """
    user = context.get("user_profile")
    # This might require checking if an 'old_email' exists in the profile
    # For now, this is a placeholder for that logic
    return True
