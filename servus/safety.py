import logging
import os
from typing import Dict, List, Tuple

import yaml

from servus.config import CONFIG

logger = logging.getLogger("servus.safety")

DEFAULT_PROTECTED_TARGETS_PATH = os.path.join("servus", "data", "protected_targets.yaml")


def _normalize_string_list(raw_values) -> List[str]:
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    if not isinstance(raw_values, list):
        return []

    normalized = []
    seen = set()
    for value in raw_values:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(lowered)
    return normalized


def _csv_values(raw_value) -> List[str]:
    if raw_value is None:
        return []
    return _normalize_string_list(str(raw_value).split(","))


def _load_protected_targets_file(path: str) -> Dict[str, List[str]]:
    if not path:
        return {"emails": [], "usernames": [], "domains": [], "departments": [], "titles_contains": []}

    if not os.path.exists(path):
        return {"emails": [], "usernames": [], "domains": [], "departments": [], "titles_contains": []}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except Exception as exc:
        logger.error("Failed to load protected targets policy file (%s): %s", path, exc)
        return {"emails": [], "usernames": [], "domains": [], "departments": [], "titles_contains": []}

    return {
        "emails": _normalize_string_list(payload.get("emails")),
        "usernames": _normalize_string_list(payload.get("usernames")),
        "domains": _normalize_string_list(payload.get("domains")),
        "departments": _normalize_string_list(payload.get("departments")),
        "titles_contains": _normalize_string_list(payload.get("titles_contains")),
    }


def load_protected_targets_policy() -> Dict[str, object]:
    """
    Build a normalized, merged protected-target policy from:
    1) YAML policy file.
    2) Optional env overrides.
    3) Safety implicit target: OFFBOARDING_ADMIN_EMAIL.
    """
    policy_path = str(CONFIG.get("PROTECTED_TARGETS_FILE") or DEFAULT_PROTECTED_TARGETS_PATH).strip()
    merged = _load_protected_targets_file(policy_path)

    merged["emails"].extend(_csv_values(CONFIG.get("PROTECTED_EMAILS")))
    merged["usernames"].extend(_csv_values(CONFIG.get("PROTECTED_USERNAMES")))
    merged["domains"].extend(_csv_values(CONFIG.get("PROTECTED_DOMAINS")))
    merged["departments"].extend(_csv_values(CONFIG.get("PROTECTED_DEPARTMENTS")))
    merged["titles_contains"].extend(_csv_values(CONFIG.get("PROTECTED_TITLES")))

    offboarding_admin_email = str(CONFIG.get("OFFBOARDING_ADMIN_EMAIL") or "").strip().lower()
    if offboarding_admin_email:
        merged["emails"].append(offboarding_admin_email)

    normalized = {
        "emails": _normalize_string_list(merged["emails"]),
        "usernames": _normalize_string_list(merged["usernames"]),
        "domains": _normalize_string_list(merged["domains"]),
        "departments": _normalize_string_list(merged["departments"]),
        "titles_contains": _normalize_string_list(merged["titles_contains"]),
    }
    normalized["path"] = policy_path
    normalized["total_rules"] = (
        len(normalized["emails"])
        + len(normalized["usernames"])
        + len(normalized["domains"])
        + len(normalized["departments"])
        + len(normalized["titles_contains"])
    )
    return normalized


def protected_policy_summary() -> Dict[str, object]:
    policy = load_protected_targets_policy()
    return {
        "path": policy["path"],
        "emails": len(policy["emails"]),
        "usernames": len(policy["usernames"]),
        "domains": len(policy["domains"]),
        "departments": len(policy["departments"]),
        "titles_contains": len(policy["titles_contains"]),
        "total_rules": policy["total_rules"],
    }


def _match_protected_rule(user_profile, policy: Dict[str, object]) -> Tuple[bool, str]:
    email = str(getattr(user_profile, "work_email", "") or "").strip().lower()
    if not email:
        return True, "work_email missing on target profile"

    if email in policy["emails"]:
        return True, f"work_email '{email}' is in protected email list"

    local_part = email.split("@", 1)[0] if "@" in email else email
    if local_part and local_part in policy["usernames"]:
        return True, f"username '{local_part}' is in protected username list"

    domain = email.split("@", 1)[1] if "@" in email else ""
    if domain and domain in policy["domains"]:
        return True, f"email domain '{domain}' is in protected domain list"

    department = str(getattr(user_profile, "department", "") or "").strip().lower()
    if department and department in policy["departments"]:
        return True, f"department '{department}' is in protected department list"

    title = str(getattr(user_profile, "title", "") or "").strip().lower()
    for token in policy["titles_contains"]:
        if token and token in title:
            return True, f"title contains protected token '{token}'"

    return False, ""


def evaluate_offboarding_target(context: dict, action_name: str = "offboarding") -> Dict[str, object]:
    user_profile = (context or {}).get("user_profile")
    if not user_profile:
        detail = "Missing user_profile in action context."
        logger.error("🛑 Offboarding safety check failed for %s: %s", action_name, detail)
        return {"ok": False, "detail": detail}

    policy = load_protected_targets_policy()
    blocked, reason = _match_protected_rule(user_profile, policy)
    email = str(getattr(user_profile, "work_email", "") or "").strip().lower()

    if blocked:
        detail = (
            f"Protected target blocked for '{email}' during '{action_name}': {reason}. "
            "No destructive action executed."
        )
        logger.error("🛑 %s", detail)
        return {"ok": False, "detail": detail}

    return {"ok": True, "detail": f"Safety checks passed for '{email}'."}
