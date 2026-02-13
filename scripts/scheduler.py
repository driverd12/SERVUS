#!/usr/bin/env python3

import csv
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import schedule

# Allow running as `python3 scripts/scheduler.py` or by absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from servus.actions import ACTIONS
from servus.config import CONFIG
from servus.core import trigger_validator
from servus.core.manual_override_queue import (
    ManualOverrideRequest,
    build_onboarding_dedupe_key,
    ensure_override_csv,
    load_ready_requests,
    mark_request_error,
    remove_request,
)
from servus.orchestrator import Orchestrator
from servus.safety import protected_policy_summary
from servus.state import RunState
from servus.workflow import load_workflow

# Configure Logging (Rotating File + Stream)
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# File Handler (10MB max, keep 5 backups)
file_handler = RotatingFileHandler("servus_scheduler.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger("servus.scheduler")

SCHEDULER_STATE_FILE = CONFIG.get("SCHEDULER_STATE_FILE", "servus_state/scheduler_state.json")
SCHEDULER_STATE_DIR = os.path.dirname(SCHEDULER_STATE_FILE)
if SCHEDULER_STATE_DIR:
    os.makedirs(SCHEDULER_STATE_DIR, exist_ok=True)

OVERRIDE_CSV_PATH = CONFIG.get("ONBOARDING_OVERRIDE_CSV", "servus_state/manual_onboarding_overrides.csv")
ensure_override_csv(OVERRIDE_CSV_PATH)

PENDING_OFFBOARD_CSV_PATH = CONFIG.get("OFFBOARDING_PENDING_CSV", "servus_state/pending_offboards.csv")

ONBOARDING_SUCCESS_KEY = "onboarding_success"
OFFBOARDING_SUCCESS_KEY = "offboarding_success"

scheduler_state = RunState(state_file=SCHEDULER_STATE_FILE)
ONBOARD_WORKFLOW_PATH = "servus/workflows/onboard_us.yaml"
OFFBOARD_WORKFLOW_PATH = "servus/workflows/offboard_us.yaml"
WORKFLOW_DIR = REPO_ROOT / "servus" / "workflows"

PENDING_OFFBOARD_COLUMNS = [
    "request_id",
    "status",
    "dedupe_key",
    "work_email",
    "first_name",
    "last_name",
    "department",
    "employment_type",
    "start_date",
    "end_date",
    "confirmation_source_a",
    "confirmation_source_b",
    "reason",
    "last_error",
    "created_at",
    "updated_at",
]


def _offboarding_execution_mode():
    """
    Returns one of: staged | auto | live.
    Backward compatible with OFFBOARDING_EXECUTION_ENABLED bool.
    """
    mode = str(CONFIG.get("OFFBOARDING_EXECUTION_MODE", "") or "").strip().lower()
    if mode in {"staged", "auto", "live"}:
        return mode
    return "live" if bool(CONFIG.get("OFFBOARDING_EXECUTION_ENABLED", False)) else "staged"


def _offboarding_live_allowed():
    mode = _offboarding_execution_mode()
    if mode == "live":
        return True, "Live mode explicitly forced by configuration."
    if mode == "staged":
        return False, "Safety-staged mode configured."

    # mode == auto
    preflight = run_startup_preflight()
    blocking = preflight.get("blocking", [])
    if blocking:
        return False, f"Auto mode paused due to blocking preflight issues: {blocking[0]}"

    protected_summary = protected_policy_summary()
    if int(protected_summary.get("total_rules", 0)) <= 0:
        return False, "Auto mode paused because protected target policy is empty."

    return True, "Auto mode checks passed; executing live offboarding."


# -----------------
# Queue CSV helpers
# -----------------

def _now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _ensure_pending_offboarding_csv(csv_path):
    directory = os.path.dirname(csv_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if os.path.exists(csv_path):
        return

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PENDING_OFFBOARD_COLUMNS)
        writer.writeheader()


def _resolved_headers(existing):
    headers = []
    seen = set()
    for header in PENDING_OFFBOARD_COLUMNS + list(existing or []):
        value = str(header or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        headers.append(value)
    return headers


def _read_pending_offboarding_rows(csv_path):
    _ensure_pending_offboarding_csv(csv_path)
    with open(csv_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = _resolved_headers(reader.fieldnames)
        rows = []
        for raw in reader:
            row = {header: str(raw.get(header) or "").strip() for header in headers}
            rows.append(row)
    return rows, headers


def _write_pending_offboarding_rows(csv_path, headers, rows):
    directory = os.path.dirname(csv_path) or "."
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(prefix=".pending_offboard_", suffix=".csv", dir=directory)
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


def _build_dual_validation_request_id(prefix, confirmation_source):
    source = str(confirmation_source or "").strip()
    token = source.split(":")[-1] if source else "unknown"
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", token)
    cleaned = cleaned.strip("-") or "unknown"
    return f"{prefix}-{cleaned}"


def _build_offboarding_dedupe_key(user_profile):
    email = (str(user_profile.work_email) if user_profile.work_email else "").strip().lower()
    end_date = str(getattr(user_profile, "end_date", "") or "").strip()
    return f"{email}|{end_date}"


def _stage_pending_offboarding(validated_trigger, status="PENDING", last_error=""):
    rows, headers = _read_pending_offboarding_rows(PENDING_OFFBOARD_CSV_PATH)

    user = validated_trigger.user_profile
    dedupe_key = _build_offboarding_dedupe_key(user)
    request_id = _build_dual_validation_request_id("OFF", validated_trigger.confirmation_source_b)
    now = _now_iso()

    for row in rows:
        if row.get("dedupe_key") != dedupe_key:
            continue
        row["status"] = status
        row["confirmation_source_a"] = validated_trigger.confirmation_source_a
        row["confirmation_source_b"] = validated_trigger.confirmation_source_b
        row["reason"] = "Dual-source departure validated"
        row["last_error"] = (last_error or "")[:500]
        row["updated_at"] = now
        if not row.get("request_id"):
            row["request_id"] = request_id
        _write_pending_offboarding_rows(PENDING_OFFBOARD_CSV_PATH, headers, rows)
        return "updated", row["request_id"]

    rows.append(
        {
            "request_id": request_id,
            "status": status,
            "dedupe_key": dedupe_key,
            "work_email": str(user.work_email),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "department": user.department,
            "employment_type": user.employment_type,
            "start_date": user.start_date or "",
            "end_date": getattr(user, "end_date", "") or "",
            "confirmation_source_a": validated_trigger.confirmation_source_a,
            "confirmation_source_b": validated_trigger.confirmation_source_b,
            "reason": "Dual-source departure validated",
            "last_error": (last_error or "")[:500],
            "created_at": now,
            "updated_at": now,
        }
    )
    _write_pending_offboarding_rows(PENDING_OFFBOARD_CSV_PATH, headers, rows)
    return "inserted", request_id


def _remove_pending_offboarding(user_profile):
    dedupe_key = _build_offboarding_dedupe_key(user_profile)
    rows, headers = _read_pending_offboarding_rows(PENDING_OFFBOARD_CSV_PATH)
    remaining = [row for row in rows if row.get("dedupe_key") != dedupe_key]
    if len(remaining) == len(rows):
        return False
    _write_pending_offboarding_rows(PENDING_OFFBOARD_CSV_PATH, headers, remaining)
    return True


# -----------------
# Workflow runners
# -----------------

def _workflow_paths_for_preflight():
    if not WORKFLOW_DIR.exists():
        return [ONBOARD_WORKFLOW_PATH, OFFBOARD_WORKFLOW_PATH]
    workflow_paths = sorted(str(path) for path in WORKFLOW_DIR.glob("*.yaml"))
    if not workflow_paths:
        return [ONBOARD_WORKFLOW_PATH, OFFBOARD_WORKFLOW_PATH]
    return workflow_paths


def run_onboarding(user_profile, trigger_source="dual_validation", request_id=None):
    """Helper to trigger the Onboarding Workflow."""
    try:
        logger.info(
            "🚀 Triggering Onboarding for %s (source=%s, request_id=%s)...",
            user_profile.work_email,
            trigger_source,
            request_id or "n/a",
        )

        wf = load_workflow(ONBOARD_WORKFLOW_PATH)
        state = RunState()
        context = {
            "config": CONFIG,
            "user_profile": user_profile,
            "dry_run": False,
            "trigger_source": trigger_source,
            "request_id": request_id,
        }

        orch = Orchestrator(wf, context, state, logger)
        result = orch.run(dry_run=False)
        success = bool(result.get("success", True)) if isinstance(result, dict) else True
        if success:
            _record_successful_onboarding(user_profile, trigger_source, request_id=request_id)
        return success
    except Exception as exc:
        logger.error("❌ Failed to run onboarding: %s", exc)
        return False


def run_offboarding(user_profile, trigger_source="dual_validation_departure", request_id=None, dry_run=False):
    """Helper to trigger the Offboarding Workflow."""
    try:
        mode = "DRY RUN" if dry_run else "LIVE"
        logger.info(
            "🛑 Triggering Offboarding (%s) for %s (source=%s, request_id=%s)...",
            mode,
            user_profile.work_email,
            trigger_source,
            request_id or "n/a",
        )

        wf = load_workflow(OFFBOARD_WORKFLOW_PATH)
        state = RunState()
        context = {
            "config": CONFIG,
            "user_profile": user_profile,
            "dry_run": dry_run,
            "trigger_source": trigger_source,
            "request_id": request_id,
        }

        orch = Orchestrator(wf, context, state, logger)
        result = orch.run(dry_run=dry_run)
        success = bool(result.get("success", True)) if isinstance(result, dict) else True
        if success and not dry_run:
            _record_successful_offboarding(user_profile, trigger_source, request_id=request_id)
        return success
    except Exception as exc:
        logger.error("❌ Failed to run offboarding: %s", exc)
        return False


def _record_successful_onboarding(user_profile, trigger_source, request_id=None):
    dedupe_key = build_onboarding_dedupe_key(user_profile)
    history = scheduler_state.get(ONBOARDING_SUCCESS_KEY, {})
    history[dedupe_key] = {
        "work_email": user_profile.work_email,
        "start_date": user_profile.start_date,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "trigger_source": trigger_source,
        "request_id": request_id,
    }
    scheduler_state.set(ONBOARDING_SUCCESS_KEY, history)


def _record_successful_offboarding(user_profile, trigger_source, request_id=None):
    dedupe_key = _build_offboarding_dedupe_key(user_profile)
    history = scheduler_state.get(OFFBOARDING_SUCCESS_KEY, {})
    history[dedupe_key] = {
        "work_email": user_profile.work_email,
        "end_date": getattr(user_profile, "end_date", None),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "trigger_source": trigger_source,
        "request_id": request_id,
    }
    scheduler_state.set(OFFBOARDING_SUCCESS_KEY, history)


def _has_successful_onboarding(user_profile):
    dedupe_key = build_onboarding_dedupe_key(user_profile)
    history = scheduler_state.get(ONBOARDING_SUCCESS_KEY, {})
    return dedupe_key in history


def _has_successful_offboarding(user_profile):
    dedupe_key = _build_offboarding_dedupe_key(user_profile)
    history = scheduler_state.get(OFFBOARDING_SUCCESS_KEY, {})
    return dedupe_key in history


# -----------------
# Manual onboarding
# -----------------

def _parse_iso_date(value):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _manual_request_ready_for_execution(request: ManualOverrideRequest, today=None):
    """
    Returns (ready: bool, reason: str, is_invalid: bool).
    """
    if CONFIG.get("MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL"):
        return True, "Global early-execution override enabled.", False

    if request.allow_before_start_date:
        return True, "Request-level early-execution override enabled.", False

    if not CONFIG.get("MANUAL_OVERRIDE_ENFORCE_START_DATE", True):
        return True, "Start-date guard disabled by config.", False

    start_date_text = (request.user_profile.start_date or "").strip()
    parsed_start = _parse_iso_date(start_date_text)
    if not parsed_start:
        return False, f"Invalid start_date format: '{start_date_text}'. Expected YYYY-MM-DD.", True

    effective_today = today or datetime.now(timezone.utc).date()
    if parsed_start > effective_today:
        return (
            False,
            f"Deferred until start_date={parsed_start.isoformat()} (today={effective_today.isoformat()}).",
            False,
        )

    return True, "Eligible by start-date policy.", False


def run_startup_preflight():
    """
    Validate action wiring and baseline runtime prerequisites.
    Returns a dict with `blocking` and `warnings` lists.
    """
    blocking = []
    warnings = []

    missing_actions = []
    workflow_paths = _workflow_paths_for_preflight()
    for workflow_path in workflow_paths:
        try:
            workflow = load_workflow(workflow_path)
        except Exception as exc:
            blocking.append(f"Failed to load workflow '{workflow_path}': {exc}")
            continue

        for step in workflow.steps:
            if step.type != "action":
                continue
            if not step.action:
                missing_actions.append(f"{workflow_path}:{step.id}:<missing-action-id>")
                continue
            if step.action not in ACTIONS:
                missing_actions.append(f"{workflow_path}:{step.id}:{step.action}")

        workflow_name = str(getattr(workflow, "name", "") or "").strip().lower()
        workflow_file = os.path.basename(str(workflow_path)).strip().lower()
        is_offboarding_workflow = "offboard" in workflow_name or "offboard" in workflow_file
        if is_offboarding_workflow:
            has_policy_gate = any(
                step.type == "action" and step.action == "builtin.validate_target_email"
                for step in workflow.steps
            )
            has_manager_gate = any(
                step.type == "action" and step.action == "okta.verify_manager_resolved"
                for step in workflow.steps
            )
            if not has_policy_gate:
                blocking.append(
                    f"Offboarding workflow '{workflow_path}' missing required action "
                    "'builtin.validate_target_email'."
                )
            if not has_manager_gate:
                blocking.append(
                    f"Offboarding workflow '{workflow_path}' missing required action "
                    "'okta.verify_manager_resolved'."
                )
    if missing_actions:
        blocking.append(f"Workflow action(s) not registered: {', '.join(missing_actions)}")

    # Core readiness checks for headless lifecycle automation.
    core_requirements = {
        "OKTA_DOMAIN": "Okta domain is required for okta.* actions",
        "OKTA_TOKEN": "Okta token is required for okta.* actions",
        "AD_HOST": "AD host is required for ad.* actions",
        "AD_USER": "AD username is required for ad.* actions",
        "AD_PASS": "AD password is required for ad.* actions",
        "SLACK_TOKEN": "Slack token is required for slack.* actions",
        "RIPPLING_API_TOKEN": "Rippling token is required for dual-validation trigger scans",
        "FRESHSERVICE_DOMAIN": "Freshservice domain is required for dual-validation trigger scans",
        "FRESHSERVICE_API_KEY": "Freshservice API key is required for dual-validation trigger scans",
    }
    for key, message in core_requirements.items():
        if not CONFIG.get(key):
            blocking.append(f"{key} missing: {message}")

    gam_path = CONFIG.get("GAM_PATH")
    gam_exists = bool(gam_path) and (os.path.exists(gam_path) or shutil.which(gam_path))
    if not gam_exists:
        blocking.append(f"GAM_PATH missing/unresolvable: '{gam_path}'")

    optional_requirements = {
        "ZOOM_ACCOUNT_ID": "Zoom account id missing; zoom.configure_user may skip/fail.",
        "ZOOM_CLIENT_ID": "Zoom client id missing; zoom.configure_user may skip/fail.",
        "ZOOM_CLIENT_SECRET": "Zoom client secret missing; zoom.configure_user may skip/fail.",
        "RAMP_API_KEY": "Ramp API key missing; ramp.configure_user will skip.",
        "LINEAR_API_KEY": "Linear API key missing; linear.provision_user may skip/fail.",
        "SQS_BADGE_QUEUE_URL": "Badge queue URL missing; brivo.provision_access may fail.",
        "SLACK_WEBHOOK_URL": "Slack webhook missing; no progress notifications will be sent.",
    }
    for key, message in optional_requirements.items():
        if not CONFIG.get(key):
            warnings.append(f"{key}: {message}")

    protected_summary = protected_policy_summary()
    if protected_summary["total_rules"] <= 0:
        warnings.append(
            "Protected target policy is empty. Populate "
            f"'{protected_summary['path']}' or SERVUS_PROTECTED_* env vars before live offboarding."
        )

    return {"blocking": blocking, "warnings": warnings}


def _process_manual_override_queue():
    requests, invalid_rows = load_ready_requests(OVERRIDE_CSV_PATH)

    for request_id, error_text in invalid_rows:
        if request_id == "missing-request-id":
            logger.error(
                "⚠️  Manual override row is invalid and missing request_id; "
                "cannot auto-mark ERROR. Fix the CSV row manually."
            )
            continue
        logger.error("⚠️  Invalid manual override request %s: %s", request_id, error_text)
        mark_request_error(OVERRIDE_CSV_PATH, request_id, error_text)

    if not requests:
        logger.info("   (No READY manual override onboarding requests found)")
        return

    logger.info("📥 Found %d READY manual override request(s)", len(requests))
    for request in requests:
        user = request.user_profile
        ready_for_execution, policy_reason, is_invalid = _manual_request_ready_for_execution(request)
        if not ready_for_execution:
            if is_invalid:
                logger.error(
                    "⚠️  Manual override request %s invalid for execution policy: %s",
                    request.request_id,
                    policy_reason,
                )
                mark_request_error(OVERRIDE_CSV_PATH, request.request_id, policy_reason)
            else:
                logger.info("🕒 Deferring manual override request %s: %s", request.request_id, policy_reason)
            continue

        if _has_successful_onboarding(user):
            logger.info(
                "♻️  Manual override already satisfied for %s; removing request %s.",
                user.work_email,
                request.request_id,
            )
            remove_request(OVERRIDE_CSV_PATH, request.request_id)
            continue

        success = run_onboarding(
            user,
            trigger_source="manual_override_csv",
            request_id=request.request_id,
        )
        if success:
            removed = remove_request(OVERRIDE_CSV_PATH, request.request_id)
            if removed:
                logger.info("🧹 Removed completed manual override request %s", request.request_id)
            else:
                logger.warning(
                    "⚠️  Manual override request %s succeeded but row was not found during dequeue.",
                    request.request_id,
                )
            continue

        logger.error(
            "❌ Manual override request %s failed. Marking row ERROR to prevent retry loops.",
            request.request_id,
        )
        mark_request_error(
            OVERRIDE_CSV_PATH,
            request.request_id,
            "onboarding execution failed; review scheduler logs and set status=READY after remediation",
        )


def _process_validated_onboarding():
    validated_triggers = trigger_validator.validate_and_fetch_onboarding_context()
    if not validated_triggers:
        logger.info("   (No validated new hires found)")
        return

    logger.info("🚀 Found %d validated new hire(s)", len(validated_triggers))
    for trigger in validated_triggers:
        user = trigger.user_profile
        if _has_successful_onboarding(user):
            logger.info("♻️  Skipping already-completed onboarding for %s", user.work_email)
            continue
        request_id = _build_dual_validation_request_id("ONB", trigger.confirmation_source_b)
        run_onboarding(user, trigger_source="dual_validation", request_id=request_id)


def _process_validated_offboarding():
    validated_triggers = trigger_validator.validate_and_fetch_offboarding_context()
    if not validated_triggers:
        logger.info("   (No validated departures found)")
        return

    execution_mode = _offboarding_execution_mode()
    execute_live, execute_reason = _offboarding_live_allowed()
    logger.info(
        "🛑 Found %d validated departure(s) [mode=%s, execute_live=%s]",
        len(validated_triggers),
        execution_mode.upper(),
        execute_live,
    )
    logger.info("   Offboarding execution decision: %s", execute_reason)

    for trigger in validated_triggers:
        user = trigger.user_profile

        if _has_successful_offboarding(user):
            logger.info("♻️  Skipping already-completed offboarding for %s", user.work_email)
            _remove_pending_offboarding(user)
            continue

        staged_action, request_id = _stage_pending_offboarding(trigger, status="PENDING")
        logger.info(
            "📄 Pending offboarding row %s for %s (request_id=%s)",
            staged_action,
            user.work_email,
            request_id,
        )

        if not execute_live:
            logger.info(
                "🧯 Offboarding safety mode active. Staged %s only; no destructive actions executed.",
                user.work_email,
            )
            continue

        success = run_offboarding(
            user,
            trigger_source="dual_validation_departure",
            request_id=request_id,
            dry_run=False,
        )
        if success:
            removed = _remove_pending_offboarding(user)
            if removed:
                logger.info("🧹 Removed completed pending offboarding row for %s", user.work_email)
            continue

        logger.error("❌ Offboarding failed for %s. Marking pending row ERROR.", user.work_email)
        _stage_pending_offboarding(
            trigger,
            status="ERROR",
            last_error="offboarding execution failed; investigate and retrigger once remediated",
        )


def job_scan_dual_validation():
    """
    Production Job: Dual-Validation Trigger (Rippling + Freshservice).
    """
    logger.info("⏰ Scheduler: Running Dual-Validation Scan...")

    try:
        _process_validated_onboarding()
        _process_validated_offboarding()
        _process_manual_override_queue()
    except Exception as exc:
        logger.error("❌ Scheduler Scan Failed: %s", exc)


def run_scheduler():
    _ensure_pending_offboarding_csv(PENDING_OFFBOARD_CSV_PATH)

    preflight = run_startup_preflight()
    for warning in preflight.get("warnings", []):
        logger.warning("⚠️ Preflight warning: %s", warning)
    if preflight.get("blocking"):
        for issue in preflight["blocking"]:
            logger.error("❌ Preflight blocking issue: %s", issue)
        if CONFIG.get("PREFLIGHT_STRICT", False):
            logger.error("🛑 PREFLIGHT_STRICT enabled. Scheduler startup aborted.")
            return
        logger.warning("⚠️ Continuing despite preflight blocking issues because PREFLIGHT_STRICT is disabled.")

    logger.info("🚀 SERVUS Scheduler Started (Production Mode).")
    logger.info("   - Dual-Validation Scan: Every 5 minutes")
    logger.info("   - Manual Override CSV: %s", OVERRIDE_CSV_PATH)
    logger.info("   - Pending Offboarding CSV: %s", PENDING_OFFBOARD_CSV_PATH)
    logger.info(
        "   - Offboarding execution mode: %s",
        _offboarding_execution_mode().upper(),
    )

    # Schedule
    schedule.every(5).minutes.do(job_scan_dual_validation)

    try:
        # Run once immediately
        job_scan_dual_validation()

        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Scheduler interrupted by operator. Exiting cleanly.")


if __name__ == "__main__":
    run_scheduler()
