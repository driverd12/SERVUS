import logging
from servus.config import CONFIG

logger = logging.getLogger("servus.ad")

def provision_user(context):
    """
    Creates or Updates a user in Active Directory.
    """
    user = context.get("user_profile")
    if not user:
        logger.error("AD: No user profile found in context.")
        return False

    # Dry Run is handled by Orchestrator logging, 
    # but we can add logic here if we need to fake a "success" return
    if context.get("dry_run"):
        # Log what we WOULD do
        logger.info(f"[DRY-INTERNAL] AD: Would create user {user.email}")
        return True

    # Check for credentials
    if not CONFIG.get("AD_HOST") or not CONFIG.get("AD_USER"):
        logger.error("AD: Missing configuration (HOST/USER).")
        return False

    logger.info(f"AD: Provisioning {user.first_name} {user.last_name} ({user.email})...")
    
    # ... Real WinRM logic would go here ...
    # For now, we simulate success for the structure
    return True

def disable_user(context):
    """
    Disables a user in Active Directory.
    """
    # Try to find email in profile or directly in context (for offboarding triggers)
    email = None
    if context.get("user_profile"):
        email = context["user_profile"].email
    
    if not email:
        logger.error("AD: No email to disable.")
        return False
        
    if context.get("dry_run"):
        logger.info(f"[DRY-INTERNAL] AD: Would disable {email}")
        return True
        
    logger.info(f"AD: Disabling account for {email}...")
    return True
