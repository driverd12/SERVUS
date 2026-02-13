from dataclasses import dataclass, field
from typing import Dict, List, Optional

from servus.integrations.okta import OktaClient
from servus.integrations.rippling import RipplingClient
from servus.models import UserProfile


@dataclass
class EnrichmentResult:
    profile_defaults: Dict[str, str] = field(default_factory=dict)
    confirmation_sources: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


def enrich_from_integrations(work_email: str) -> EnrichmentResult:
    result = EnrichmentResult()
    normalized_email = (work_email or "").strip().lower()
    if not normalized_email:
        return result

    rippling_profile = _lookup_rippling_profile(normalized_email)
    if rippling_profile:
        result.profile_defaults.update(_profile_to_defaults(rippling_profile))
        result.confirmation_sources.append(f"rippling:work_email:{normalized_email}")
        result.evidence.append("rippling_profile_match")

    okta_user = _lookup_okta_user(normalized_email)
    if okta_user:
        profile = okta_user.get("profile") if isinstance(okta_user, dict) else {}
        if isinstance(profile, dict):
            manager = profile.get("manager")
            if isinstance(manager, str) and "@" in manager:
                result.profile_defaults.setdefault("manager_email", manager.strip().lower())
            manager_mail = profile.get("managerMail")
            if isinstance(manager_mail, str) and "@" in manager_mail:
                result.profile_defaults.setdefault("manager_email", manager_mail.strip().lower())
            title = profile.get("title")
            if isinstance(title, str) and title.strip():
                result.profile_defaults.setdefault("title", title.strip())
            first_name = profile.get("firstName")
            if isinstance(first_name, str) and first_name.strip():
                result.profile_defaults.setdefault("first_name", first_name.strip())
            last_name = profile.get("lastName")
            if isinstance(last_name, str) and last_name.strip():
                result.profile_defaults.setdefault("last_name", last_name.strip())
            department = profile.get("department")
            if isinstance(department, str) and department.strip():
                result.profile_defaults.setdefault("department", department.strip())
            start_date = profile.get("startDate")
            if isinstance(start_date, str) and start_date.strip():
                result.profile_defaults.setdefault("start_date", start_date.strip())

            employment_type = _map_okta_employment_type(profile)
            if employment_type:
                result.profile_defaults.setdefault("employment_type", employment_type)

        okta_id = okta_user.get("id") if isinstance(okta_user, dict) else None
        suffix = okta_id if isinstance(okta_id, str) and okta_id.strip() else normalized_email
        result.confirmation_sources.append(f"okta:user:{suffix}")
        result.evidence.append("okta_user_lookup")

    # Deduplicate while preserving order.
    deduped_sources = []
    seen = set()
    for source in result.confirmation_sources:
        key = source.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_sources.append(source)
    result.confirmation_sources = deduped_sources

    return result


def _lookup_rippling_profile(work_email: str) -> Optional[UserProfile]:
    client = RipplingClient()
    if not client.token:
        return None
    return client.find_user_by_email(work_email)


def _lookup_okta_user(work_email: str) -> Optional[Dict[str, object]]:
    client = OktaClient()
    if not client.domain or not client.token:
        return None
    user = client.get_user(work_email)
    return user if isinstance(user, dict) else None


def _profile_to_defaults(profile: UserProfile) -> Dict[str, str]:
    defaults: Dict[str, str] = {}
    for key in [
        "first_name",
        "last_name",
        "work_email",
        "department",
        "employment_type",
        "start_date",
        "end_date",
        "personal_email",
        "title",
        "manager_email",
        "location",
    ]:
        value = getattr(profile, key, None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            defaults[key] = text
    return defaults


def _map_okta_employment_type(profile: Dict[str, object]) -> Optional[str]:
    raw = profile.get("hrEmploymentType") or profile.get("employeeType")
    if not isinstance(raw, str):
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    lower = normalized.lower()
    if "contract" in lower:
        return "Contractor"
    if "intern" in lower:
        return "Intern"
    if "supplier" in lower:
        return "Supplier"
    return "Full-Time"
