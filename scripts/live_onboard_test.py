#!/usr/bin/env python3
"""
Queue a manual onboarding request for headless scheduler processing.

This script replaces direct one-off onboarding execution. It writes a validated
`READY` row into the manual override CSV queue so unattended SERVUS can process
it in the normal scheduler loop.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Allow running as `python3 scripts/live_onboard_test.py` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from servus.config import CONFIG
from servus.core.manual_override_queue import (
    ManualOverrideRequest,
    enqueue_request,
    ensure_override_csv,
)
from servus.models import UserProfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("manual_onboard_queue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Queue a manual onboarding request into the SERVUS override CSV."
    )
    parser.add_argument(
        "--csv-path",
        default=CONFIG.get("ONBOARDING_OVERRIDE_CSV", "servus_state/manual_onboarding_overrides.csv"),
        help="Path to manual override CSV queue",
    )
    parser.add_argument(
        "--profile-json",
        help="Optional JSON profile path. Supports old one-off keys (first,last,email,dept,type,manager) and UserProfile keys.",
    )
    parser.add_argument("--request-id", help="Unique request id. Auto-generated if omitted.")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument("--work-email")
    parser.add_argument("--department")
    parser.add_argument("--employment-type")
    parser.add_argument("--start-date", help="YYYY-MM-DD recommended")
    parser.add_argument("--personal-email")
    parser.add_argument("--title")
    parser.add_argument("--manager-email")
    parser.add_argument("--location", default="US")
    parser.add_argument("--confirmation-source-a", required=True)
    parser.add_argument("--confirmation-source-b", required=True)
    parser.add_argument("--reason", default="")
    parser.add_argument(
        "--allow-update",
        action="store_true",
        help="Update existing request_id row instead of failing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print request without writing CSV",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Deprecated. Direct live execution is no longer supported by this script.",
    )
    return parser.parse_args()


def build_user_profile(args: argparse.Namespace) -> UserProfile:
    profile_data: Dict[str, Any] = {}
    if args.profile_json:
        profile_data = load_profile_json(args.profile_json)

    kwargs = {
        "first_name": args.first_name or profile_data.get("first_name"),
        "last_name": args.last_name or profile_data.get("last_name"),
        "work_email": args.work_email or profile_data.get("work_email"),
        "department": args.department or profile_data.get("department"),
        "employment_type": args.employment_type or profile_data.get("employment_type"),
        "start_date": args.start_date or profile_data.get("start_date"),
        "personal_email": args.personal_email or profile_data.get("personal_email"),
        "title": args.title or profile_data.get("title"),
        "manager_email": args.manager_email or profile_data.get("manager_email"),
        "location": args.location or profile_data.get("location") or "US",
    }

    missing = [key for key in ["first_name", "last_name", "work_email", "department", "employment_type", "start_date"] if not kwargs.get(key)]
    if missing:
        raise ValueError(f"Missing required profile fields: {', '.join(missing)}")

    return UserProfile(**kwargs)


def load_profile_json(path: str) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile JSON must be an object")

    return {
        "first_name": payload.get("first_name") or payload.get("first"),
        "last_name": payload.get("last_name") or payload.get("last"),
        "work_email": payload.get("work_email") or payload.get("email"),
        "department": payload.get("department") or payload.get("dept"),
        "employment_type": payload.get("employment_type") or payload.get("type"),
        "start_date": payload.get("start_date"),
        "personal_email": payload.get("personal_email"),
        "title": payload.get("title"),
        "manager_email": payload.get("manager_email") or payload.get("manager"),
        "location": payload.get("location") or "US",
    }


def generate_request_id(work_email: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    local = work_email.split("@", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", local).strip("-") or "manual"
    return f"REQ-{timestamp}-{slug}"


def main() -> int:
    args = parse_args()
    if args.live:
        logger.error(
            "--live is deprecated for safety. This script only queues requests for headless scheduler execution."
        )
        return 2

    try:
        user = build_user_profile(args)
        request_id = args.request_id or generate_request_id(str(user.work_email))
        request = ManualOverrideRequest(
            request_id=request_id,
            user_profile=user,
            confirmation_source_a=args.confirmation_source_a.strip(),
            confirmation_source_b=args.confirmation_source_b.strip(),
            reason=args.reason.strip() or None,
        )

        if args.dry_run:
            logger.info("Dry-run validation passed.")
            logger.info("Would enqueue request_id=%s email=%s csv=%s", request_id, user.work_email, args.csv_path)
            return 0

        ensure_override_csv(args.csv_path)
        action = enqueue_request(args.csv_path, request, allow_update=args.allow_update)
        logger.info(
            "Queued manual onboarding request (%s): request_id=%s email=%s csv=%s",
            action,
            request_id,
            user.work_email,
            args.csv_path,
        )
        logger.info("Scheduler will pick this up on the next polling cycle.")
        return 0
    except Exception as exc:
        logger.error("Failed to queue manual onboarding request: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
