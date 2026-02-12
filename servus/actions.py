# Import all integration modules
from .integrations import ad
from .integrations import okta
from .integrations import google_gam
from .integrations import slack
from .integrations import zoom
from .integrations import ramp
from .integrations import linear
from .integrations import apple
from .integrations import brivo
from . import actions_builtin as builtin


def _apple_check_device_assignment(context):
    """
    Workflow wrapper for Apple ABM checks.
    Existing Apple integration expects a serial number argument, so we adapt
    it to workflow action context without changing integration API semantics.
    """
    if not isinstance(context, dict):
        return False
    if context.get("dry_run"):
        return True

    serial_number = context.get("device_serial_number") or context.get("serial_number")
    if not serial_number:
        # No serial in onboarding payload is an idempotent skip, not a failure.
        return {"ok": True, "detail": "No device serial provided; skipping ABM check."}

    result = apple.check_device_assignment(str(serial_number))
    if isinstance(result, dict):
        return result
    return bool(result)

# Registry mapping YAML strings to Python functions
ACTIONS = {
    # Built-in Logic
    "builtin.validate_profile": builtin.validate_profile,
    "builtin.validate_target_email": builtin.validate_target_email,
    
    # Active Directory
    "ad.provision_user": ad.validate_user_exists, # Remapped since we don't provision anymore
    "ad.validate_user_exists": ad.validate_user_exists,
    "ad.verify_user_disabled": ad.ensure_user_disabled, # Remapped to the new safety net function
    "ad.ensure_user_disabled": ad.ensure_user_disabled,
    
    # Okta
    "okta.find_user": okta.wait_for_user, # Remapped to wait loop
    "okta.assign_apps": okta.assign_custom_groups, # Remapped to group assignment
    "okta.deactivate_user": okta.deactivate_user,
    "okta.verify_manager_resolved": okta.verify_manager_resolved,
    
    # Google (GAM)
    "google_gam.wait_for_user_scim": google_gam.wait_for_user_scim,
    "google_gam.move_user_ou": google_gam.move_user_ou,
    "google_gam.add_groups": google_gam.add_groups,
    "google_gam.deprovision_user": google_gam.deprovision_user,
    "google_gam.process_rehire": google_gam.process_rehire,
    
    # Slack
    "slack.add_to_channels": slack.add_to_channels,
    "slack.deactivate_user": slack.deactivate_user,

    # Zoom
    "zoom.configure_user": zoom.configure_user,

    # Ramp
    "ramp.configure_user": ramp.configure_user,

    # Linear
    "linear.provision_user": linear.provision_user,
    "linear.verify_deprovisioned": linear.verify_deprovisioned,

    # Apple ABM
    "apple.check_device_assignment": _apple_check_device_assignment,

    # Brivo / Badge queue
    "brivo.provision_access": brivo.provision_access,
}
