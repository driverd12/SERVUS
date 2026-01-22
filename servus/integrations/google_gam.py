import os
import subprocess
import logging
from servus.config import CONFIG

logger = logging.getLogger("servus.gam")

def _run_gam(args, context=None):
    """
    Internal helper to run GAM commands securely.
    Includes a 'belt-and-suspenders' check for dry_run context.
    """
    # SAFETY CHECK: If context says dry_run, abort immediately.
    if context and context.get('dry_run', False):
        logger.info(f"[DRY-RUN-INTERNAL] Would have run GAM command: gam {' '.join(args)}")
        return True

    gam_path = CONFIG.get("GAM_PATH", "gam")
    
    # Validation
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
    """
    user = context.get("user_profile")
    if not user: return False

    email = user.email
    
    # Logic for Target OU
    if user.user_type == "CON":
        target_ou = "/New Users - Contractors"
    elif user.user_type == "INT":
        target_ou = "/New Users - Interns"
    else:
        target_ou = "/New Users - FTE"

    logger.info(f"Moving {email} to Google OU: {target_ou}")
    
    # Pass context to _run_gam for safety check
    return _run_gam(["update", "user", email, "org", target_ou], context)

def add_to_groups(context):
    """
    Adds user to standard distribution lists.
    """
    user = context.get("user_profile")
    if not user: return False

    email = user.email
    groups_to_add = []

    if user.user_type == "FTE":
        groups_to_add.append("team@boom.aero")
    elif user.user_type == "CON":
        groups_to_add.append("contractors@boom.aero")
    
    success = True
    for group in groups_to_add:
        logger.info(f"Adding {email} to Google Group: {group}")
        if not _run_gam(["update", "group", group, "add", "member", email], context):
            success = False
            
    return success

def suspend_user(context):
    """
    Suspends a user in Google Workspace (Offboarding).
    """
    # For offboarding, the context usually has 'email' directly or a partial profile
    email = context.get("email") or (context.get("user_profile") and context.get("user_profile").email)
    
    if not email:
        logger.error("No email provided for suspension.")
        return False

    logger.info(f"Suspending Google User: {email}")
    return _run_gam(["update", "user", email, "suspended", "on"], context)
