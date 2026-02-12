import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from servus.models import UserProfile

READY_STATUS = "READY"
ERROR_STATUS = "ERROR"

REQUIRED_COLUMNS = [
    "request_id",
    "work_email",
    "first_name",
    "last_name",
    "department",
    "employment_type",
    "start_date",
    "confirmation_source_a",
    "confirmation_source_b",
]

BASE_COLUMNS = [
    "request_id",
    "status",
    "work_email",
    "first_name",
    "last_name",
    "department",
    "employment_type",
    "start_date",
    "personal_email",
    "title",
    "manager_email",
    "location",
    "confirmation_source_a",
    "confirmation_source_b",
    "reason",
    "last_error",
    "created_at",
    "updated_at",
]


@dataclass
class ManualOverrideRequest:
    request_id: str
    user_profile: UserProfile
    confirmation_source_a: str
    confirmation_source_b: str
    reason: Optional[str]

    @property
    def dedupe_key(self) -> str:
        return build_onboarding_dedupe_key(self.user_profile)

    def to_row(self, status: str = READY_STATUS) -> Dict[str, str]:
        now = _now_iso()
        return {
            "request_id": self.request_id,
            "status": status,
            "work_email": str(self.user_profile.work_email),
            "first_name": self.user_profile.first_name,
            "last_name": self.user_profile.last_name,
            "department": self.user_profile.department,
            "employment_type": self.user_profile.employment_type,
            "start_date": self.user_profile.start_date or "",
            "personal_email": str(self.user_profile.personal_email or ""),
            "title": self.user_profile.title or "",
            "manager_email": str(self.user_profile.manager_email or ""),
            "location": self.user_profile.location or "US",
            "confirmation_source_a": self.confirmation_source_a,
            "confirmation_source_b": self.confirmation_source_b,
            "reason": self.reason or "",
            "last_error": "",
            "created_at": now,
            "updated_at": now,
        }


def ensure_override_csv(csv_path: str) -> None:
    directory = os.path.dirname(csv_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    if os.path.exists(csv_path):
        return

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BASE_COLUMNS)
        writer.writeheader()


def load_ready_requests(csv_path: str) -> Tuple[List[ManualOverrideRequest], List[Tuple[str, str]]]:
    ensure_override_csv(csv_path)
    rows, _headers = _read_rows(csv_path)

    ready: List[ManualOverrideRequest] = []
    invalid: List[Tuple[str, str]] = []

    for row in rows:
        status = (row.get("status") or READY_STATUS).strip().upper()
        if status != READY_STATUS:
            continue

        request_id = (row.get("request_id") or "").strip()
        if not request_id:
            invalid.append(("missing-request-id", "request_id is required"))
            continue

        try:
            ready.append(_parse_request(row))
        except Exception as exc:
            invalid.append((request_id, str(exc)))

    return ready, invalid


def enqueue_request(
    csv_path: str,
    request: ManualOverrideRequest,
    *,
    allow_update: bool = False,
) -> str:
    """
    Insert a READY request row into the override queue.
    Returns "inserted" or "updated".
    """
    # Validate before writing.
    _parse_request(request.to_row(status=READY_STATUS))

    rows, headers = _read_rows(csv_path)
    now = _now_iso()
    request_id = request.request_id
    incoming_row = request.to_row(status=READY_STATUS)

    for index, row in enumerate(rows):
        if _row_request_id(row) != request_id:
            continue
        if not allow_update:
            raise ValueError(f"request_id already exists: {request_id}")
        incoming_row["created_at"] = row.get("created_at") or now
        incoming_row["updated_at"] = now
        rows[index] = incoming_row
        _write_rows(csv_path, headers, rows)
        return "updated"

    rows.append(incoming_row)
    _write_rows(csv_path, headers, rows)
    return "inserted"


def remove_request(csv_path: str, request_id: str) -> bool:
    rows, headers = _read_rows(csv_path)
    before = len(rows)
    remaining = [row for row in rows if _row_request_id(row) != request_id]
    if len(remaining) == before:
        return False
    _write_rows(csv_path, headers, remaining)
    return True


def mark_request_error(csv_path: str, request_id: str, error_text: str) -> bool:
    rows, headers = _read_rows(csv_path)
    updated = False
    now = _now_iso()

    for row in rows:
        if _row_request_id(row) != request_id:
            continue
        row["status"] = ERROR_STATUS
        row["last_error"] = (error_text or "")[:500]
        row["updated_at"] = now
        if not row.get("created_at"):
            row["created_at"] = now
        updated = True
        break

    if updated:
        _write_rows(csv_path, headers, rows)
    return updated


def build_onboarding_dedupe_key(user_profile: UserProfile) -> str:
    email = (user_profile.work_email or "").strip().lower()
    start_date = (user_profile.start_date or "").strip().lower()
    return f"{email}|{start_date}"


def _parse_request(row: Dict[str, str]) -> ManualOverrideRequest:
    for column in REQUIRED_COLUMNS:
        value = (row.get(column) or "").strip()
        if not value:
            raise ValueError(f"{column} is required")

    source_a = (row.get("confirmation_source_a") or "").strip()
    source_b = (row.get("confirmation_source_b") or "").strip()
    if source_a.lower() == source_b.lower():
        raise ValueError("confirmation_source_a and confirmation_source_b must be distinct")

    user = UserProfile(
        first_name=(row.get("first_name") or "").strip(),
        last_name=(row.get("last_name") or "").strip(),
        work_email=(row.get("work_email") or "").strip(),
        personal_email=_optional_value(row.get("personal_email")),
        department=(row.get("department") or "").strip(),
        title=_optional_value(row.get("title")),
        manager_email=_optional_value(row.get("manager_email")),
        employment_type=(row.get("employment_type") or "").strip(),
        start_date=_optional_value(row.get("start_date")),
        location=_optional_value(row.get("location")) or "US",
    )

    return ManualOverrideRequest(
        request_id=(row.get("request_id") or "").strip(),
        user_profile=user,
        confirmation_source_a=source_a,
        confirmation_source_b=source_b,
        reason=_optional_value(row.get("reason")),
    )


def _optional_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _read_rows(csv_path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    ensure_override_csv(csv_path)
    with open(csv_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = _resolved_headers(reader.fieldnames or [])
        rows: List[Dict[str, str]] = []
        for raw in reader:
            row = {header: (raw.get(header) or "").strip() for header in headers}
            rows.append(row)
    return rows, headers


def _resolved_headers(existing: List[str]) -> List[str]:
    headers: List[str] = []
    seen = set()

    for header in BASE_COLUMNS + existing:
        normalized = (header or "").strip()
        if not normalized or normalized in seen:
            continue
        headers.append(normalized)
        seen.add(normalized)

    return headers


def _write_rows(csv_path: str, headers: List[str], rows: List[Dict[str, str]]) -> None:
    directory = os.path.dirname(csv_path) or "."
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(prefix=".override_tmp_", suffix=".csv", dir=directory)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({header: row.get(header, "") for header in headers})
        os.replace(temp_path, csv_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _row_request_id(row: Dict[str, str]) -> str:
    return (row.get("request_id") or "").strip()


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
