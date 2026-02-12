#!/usr/bin/env python3

import sys
from pathlib import Path

# Allow running as `python3 scripts/scheduler.py` or by absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time
import os
import logging
import shutil
import schedule
from datetime import datetime, timezone, date
from logging.handlers import RotatingFileHandler
from servus.orchestrator import Orchestrator
from servus.state import RunState
from servus.workflow import load_workflow
from servus.config import CONFIG
from servus.actions import ACTIONS
from servus.core import trigger_validator
from servus.core.manual_override_queue import (
    ManualOverrideRequest,
    build_onboarding_dedupe_key,
    ensure_override_csv,
    load_ready_requests,
    mark_request_error,
    remove_request,
)

# Configure Logging (Rotating File + Stream)
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# File Handler (10MB max, keep 5 backups)
file_handler = RotatingFileHandler("servus_scheduler.log", maxBytes=10*1024*1024, backupCount=5)
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

ONBOARDING_SUCCESS_KEY = "onboarding_success"
scheduler_state = RunState(state_file=SCHEDULER_STATE_FILE)
ONBOARD_WORKFLOW_PATH = "servus/workflows/onboard_us.yaml"
WORKFLOW_DIR = REPO_ROOT / "servus" / "workflows"


def _workflow_paths_for_preflight():
    if not WORKFLOW_DIR.exists():
        return [ONBOARD_WORKFLOW_PATH]
    workflow_paths = sorted(str(path) for path in WORKFLOW_DIR.glob("*.yaml"))
    if not workflow_paths:
        return [ONBOARD_WORKFLOW_PATH]
    return workflow_paths


def run_onboarding(user_profile, trigger_source="dual_validation", request_id=None):
    """Helper to trigger the Onboarding Workflow"""
    try:
        logger.info(
            f"🚀 Triggering Onboarding for {user_profile.work_email} "
            f"(source={trigger_source}, request_id={request_id or 'n/a'})..."
        )

        wf = load_workflow("servus/workflows/onboard_us.yaml")
        state = RunState()
        context = {
            "config": CONFIG,
            "user_profile": user_profile,
            "dry_run": False, # Production is LIVE
            "trigger_source": trigger_source,
            "request_id": request_id,
        }
        
        orch = Orchestrator(wf, context, state, logger)
        result = orch.run(dry_run=False)
        success = bool(result.get("success", True)) if isinstance(result, dict) else True
        if success:
            _record_successful_onboarding(user_profile, trigger_source, request_id=request_id)
        return success
    except Exception as e:
        logger.error(f"❌ Failed to run onboarding: {e}")
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


def _has_successful_onboarding(user_profile):
    dedupe_key = build_onboarding_dedupe_key(user_profile)
    history = scheduler_state.get(ONBOARDING_SUCCESS_KEY, {})
    return dedupe_key in history


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
    if missing_actions:
        blocking.append(f"Workflow action(s) not registered: {', '.join(missing_actions)}")

    # Core readiness checks (blocking): onboarding core systems.
    core_requirements = {
        "OKTA_DOMAIN": "Okta domain is required for okta.* actions",
        "OKTA_TOKEN": "Okta token is required for okta.* actions",
        "AD_HOST": "AD host is required for ad.* actions",
        "AD_USER": "AD username is required for ad.* actions",
        "AD_PASS": "AD password is required for ad.* actions",
        "SLACK_TOKEN": "Slack token is required for slack.* actions",
    }
    for key, message in core_requirements.items():
        if not CONFIG.get(key):
            blocking.append(f"{key} missing: {message}")

    gam_path = CONFIG.get("GAM_PATH")
    gam_exists = bool(gam_path) and (os.path.exists(gam_path) or shutil.which(gam_path))
    if not gam_exists:
        blocking.append(f"GAM_PATH missing/unresolvable: '{gam_path}'")

    # Optional integrations used in onboarding workflow (warnings only).
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
        logger.error(f"⚠️  Invalid manual override request {request_id}: {error_text}")
        mark_request_error(OVERRIDE_CSV_PATH, request_id, error_text)

    if not requests:
        logger.info("   (No READY manual override onboarding requests found)")
        return

    logger.info(f"📥 Found {len(requests)} READY manual override request(s)")
    for request in requests:
        user = request.user_profile
        ready_for_execution, policy_reason, is_invalid = _manual_request_ready_for_execution(request)
        if not ready_for_execution:
            if is_invalid:
                logger.error(
                    f"⚠️  Manual override request {request.request_id} invalid for execution policy: {policy_reason}"
                )
                mark_request_error(OVERRIDE_CSV_PATH, request.request_id, policy_reason)
            else:
                logger.info(f"🕒 Deferring manual override request {request.request_id}: {policy_reason}")
            continue

        if _has_successful_onboarding(user):
            logger.info(
                f"♻️  Manual override already satisfied for {user.work_email}; removing request {request.request_id}."
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
                logger.info(f"🧹 Removed completed manual override request {request.request_id}")
            else:
                logger.warning(
                    f"⚠️  Manual override request {request.request_id} succeeded but row was not found during dequeue."
                )
            continue

        logger.error(
            f"❌ Manual override request {request.request_id} failed. Marking row ERROR to prevent retry loops."
        )
        mark_request_error(
            OVERRIDE_CSV_PATH,
            request.request_id,
            "onboarding execution failed; review scheduler logs and set status=READY after remediation",
        )

def job_scan_dual_validation():
    """
    Production Job: Dual-Validation Trigger (Rippling + Freshservice).
    """
    logger.info("⏰ Scheduler: Running Dual-Validation Scan...")
    
    try:
        # Use the new core validator
        valid_users = trigger_validator.validate_and_fetch_context()
        
        if valid_users:
            logger.info(f"🚀 Found {len(valid_users)} validated new hires!")
            for user in valid_users:
                if _has_successful_onboarding(user):
                    logger.info(f"♻️  Skipping already-completed onboarding for {user.work_email}")
                    continue
                run_onboarding(user, trigger_source="dual_validation")
        else:
            logger.info("   (No validated new hires found)")

        _process_manual_override_queue()
    except Exception as e:
        logger.error(f"❌ Scheduler Scan Failed: {e}")

def run_scheduler():
    preflight = run_startup_preflight()
    for warning in preflight.get("warnings", []):
        logger.warning(f"⚠️ Preflight warning: {warning}")
    if preflight.get("blocking"):
        for issue in preflight["blocking"]:
            logger.error(f"❌ Preflight blocking issue: {issue}")
        if CONFIG.get("PREFLIGHT_STRICT", False):
            logger.error("🛑 PREFLIGHT_STRICT enabled. Scheduler startup aborted.")
            return
        logger.warning("⚠️ Continuing despite preflight blocking issues because PREFLIGHT_STRICT is disabled.")

    logger.info("🚀 SERVUS Scheduler Started (Production Mode).")
    logger.info("   - Dual-Validation Scan: Every 5 minutes")
    logger.info(f"   - Manual Override CSV: {OVERRIDE_CSV_PATH}")
    
    # Schedule
    schedule.every(5).minutes.do(job_scan_dual_validation)
    
    # Run once immediately
    job_scan_dual_validation()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
