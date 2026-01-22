import logging

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
    # Logic for offboarding validation
    return True
