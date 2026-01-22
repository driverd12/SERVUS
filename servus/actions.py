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
    "ad.provision_user": ad.provision_user,
    "ad.disable_user": ad.disable_user,
    
    # Okta
    "okta.trigger_ad_import": okta.trigger_ad_import,
    "okta.find_user": okta.find_user,
    "okta.assign_apps": okta.assign_apps,
    "okta.deactivate_user": okta.deactivate_user,
    
    # Google (GAM)
    "google_gam.move_user_ou": google_gam.move_user_ou,
    "google_gam.add_to_groups": google_gam.add_to_groups,
    "google_gam.suspend_user": google_gam.suspend_user,
    
    # Slack
    "slack.add_to_channels": slack.add_to_channels,
}
