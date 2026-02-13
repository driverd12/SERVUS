import logging
from servus.safety import evaluate_offboarding_target

logger = logging.getLogger("servus.builtin")

def validate_profile(context):
    user = context.get('user_profile')
    if not user:
        logger.error("Context missing 'user_profile'")
        return False
        
    logger.info(f"Validating User: {user.first_name} {user.last_name} ({user.email})")
    
    if not user.email.endswith("@boom.aero"):
        logger.error("Email must end with @boom.aero")
        return False
        
    return True

def validate_target_email(context):
    """
    Offboarding safety gate:
    1) Validate target email domain.
    2) Block protected targets before destructive actions.
    """
    user = context.get("user_profile") if isinstance(context, dict) else None
    if not user:
        logger.error("Context missing 'user_profile'")
        return {"ok": False, "detail": "Missing user_profile in action context."}

    email = str(getattr(user, "work_email", "") or "").strip().lower()
    if not email:
        logger.error("Target profile missing work_email")
        return {"ok": False, "detail": "Target profile missing work_email."}

    if not email.endswith("@boom.aero"):
        logger.error("Offboarding blocked: target email outside corporate domain (%s)", email)
        return {
            "ok": False,
            "detail": f"Offboarding blocked for non-corporate email '{email}'.",
        }

    action_name = context.get("offboarding_action_name") if isinstance(context, dict) else None
    return evaluate_offboarding_target(context, action_name=action_name or "builtin.validate_target_email")
