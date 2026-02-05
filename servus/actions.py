# Import all integration modules
from .integrations import ad
from .integrations import okta
from .integrations import google_gam
from .integrations import slack
from . import actions_builtin as builtin

# Registry mapping YAML strings to Python functions
ACTIONS = {
    # Built-in Logic
    "builtin.validate_profile": builtin.validate_profile,
    "builtin.validate_target_email": builtin.validate_target_email,
    
    # Active Directory
    "ad.provision_user": ad.validate_user_exists, # Remapped since we don't provision anymore
    "ad.validate_user_exists": ad.validate_user_exists,
    "ad.verify_user_disabled": ad.verify_user_disabled,
    
    # Okta
    "okta.find_user": okta.wait_for_user, # Remapped to wait loop
    "okta.assign_apps": okta.assign_custom_groups, # Remapped to group assignment
    "okta.deactivate_user": okta.deactivate_user,
    
    # Google (GAM)
    "google_gam.move_user_ou": google_gam.move_user_ou,
    "google_gam.add_groups": google_gam.add_groups,
    "google_gam.deprovision_user": google_gam.deprovision_user,
    
    # Slack
    "slack.add_to_channels": slack.add_to_channels,
    "slack.deactivate_user": slack.deactivate_user,
}
