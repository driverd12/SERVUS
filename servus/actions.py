from __future__ import annotations
from typing import Callable, Any

from . import actions_builtin
from .integrations import ad as ad_mod
from .integrations import okta as okta_mod

# Map action string -> callable
ACTIONS: dict[str, Callable[..., dict[str, Any]]] = {
    "builtin.noop": actions_builtin.noop,
    "builtin.wait": actions_builtin.wait,
    "builtin.manual": actions_builtin.manual,
    "builtin.validate_profile": actions_builtin.validate_profile,

    "ad.provision_user": ad_mod.provision_user,
    "ad.verify_user": ad_mod.verify_user,
    "ad.disable_user": ad_mod.disable_user,

    "okta.trigger_ad_import": okta_mod.trigger_ad_import,
    "okta.find_user": okta_mod.find_user,
    "okta.assign_apps": okta_mod.assign_apps,
    "okta.deactivate_user": okta_mod.deactivate_user,
}
