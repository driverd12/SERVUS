import logging
from servus.config import CONFIG
from servus.integrations import badge_queue
from servus.integrations.okta import OktaClient
from servus.integrations.rippling import RipplingClient
from servus.notifier import SlackNotifier

logger = logging.getLogger("servus.brivo")

class BrivoClient:
    def __init__(self):
        # API Client Deprecated - Only used for legacy/future reference if needed
        # We now use badge_queue for printing and assume manual/SCIM for management
        pass

    def login(self):
        logger.warning("⚠️ Brivo API Login is deprecated.")
        return False

    def find_user(self, email):
        logger.warning("⚠️ Brivo API User Search is deprecated.")
        return None

    def wait_for_user_scim(self, email):
        logger.warning("⚠️ Brivo SCIM Wait is deprecated.")
        return None

# --- WORKFLOW ACTIONS ---

def provision_access(context):
    """
    Triggers badge print job with user metadata.
    Note: Brivo user creation/binding is now MANUAL or handled by SCIM separately.
    This step only pushes the print job to the queue.
    """
    user = context.get("user_profile")
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would queue badge print job for {user.work_email}")
        return {"ok": True, "detail": "Dry run: would queue badge print job."}

    if not CONFIG.get("SQS_BADGE_QUEUE_URL"):
        logger.warning("⚠️ Brivo badge queue URL missing. Falling back to manual Slack action.")
        _notify_manual_brivo_badge_action(
            context,
            user,
            reason="SQS_BADGE_QUEUE_URL is not configured.",
        )
        return {
            "ok": True,
            "detail": "Badge queue unavailable; posted manual Brivo/badge action to Slack.",
        }

    logger.info("🖨️  Queueing Badge Print Job (Metadata Push)...")
    
    # Prepare data for the queue
    # We pass the profile data directly. The badge_queue module handles extraction.
    user_data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.work_email,
        "preferred_first_name": user.preferred_first_name,
        "profile_picture_url": user.profile_picture_url
    }
    
    queued = badge_queue.send_print_job(user_data)
    if queued:
        return {"ok": True, "detail": "Queued badge print job to SQS successfully."}

    _notify_manual_brivo_badge_action(
        context,
        user,
        reason="Failed to queue badge print job to SQS.",
    )
    return {
        "ok": True,
        "detail": "Badge queue failed; posted manual Brivo/badge action to Slack.",
    }

def suspend_user(context):
    """
    Suspends a user in Brivo (Revokes badge access).
    Note: Deprecated API usage. Should rely on SCIM.
    """
    logger.warning("🚫 Brivo: Suspend User is deprecated (Use SCIM).")
    return True


def _notify_manual_brivo_badge_action(context, user, reason):
    notifier = SlackNotifier()
    profile_image_url = _resolve_profile_image_url(user)
    full_name = f"{user.first_name} {user.last_name}".strip()
    notifier.notify_badge_manual_action(
        user_email=str(user.work_email),
        full_name=full_name,
        title=user.title,
        manager_email=str(user.manager_email or ""),
        profile_image_url=profile_image_url,
        reason=reason,
        trigger_source=context.get("trigger_source"),
        request_id=context.get("request_id"),
    )


def _resolve_profile_image_url(user):
    existing_url = str(getattr(user, "profile_picture_url", "") or "").strip()
    if existing_url:
        return existing_url

    work_email = str(getattr(user, "work_email", "") or "").strip().lower()
    if not work_email:
        return None

    try:
        rippling = RipplingClient()
        if rippling.token:
            profile = rippling.find_user_by_email(work_email)
            candidate = str(getattr(profile, "profile_picture_url", "") or "").strip()
            if candidate:
                return candidate
    except Exception as exc:
        logger.warning("Could not resolve Rippling profile image for %s: %s", work_email, exc)

    try:
        okta = OktaClient()
        if okta.domain and okta.token:
            okta_user = okta.get_user(work_email)
            profile = okta_user.get("profile") if isinstance(okta_user, dict) else {}
            if isinstance(profile, dict):
                candidate = (
                    str(profile.get("profileUrl") or profile.get("photoUrl") or "").strip()
                )
                if candidate:
                    return candidate
    except Exception as exc:
        logger.warning("Could not resolve Okta profile image for %s: %s", work_email, exc)

    return None
