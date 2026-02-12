import time
import os
import logging
import schedule
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from servus.orchestrator import Orchestrator
from servus.state import RunState
from servus.workflow import load_workflow
from servus.config import CONFIG
from servus.core import trigger_validator
from servus.core.manual_override_queue import (
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
            "dry_run": False # Production is LIVE
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
