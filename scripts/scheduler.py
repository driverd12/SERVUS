import time
import logging
import schedule
from logging.handlers import RotatingFileHandler
from servus.orchestrator import Orchestrator
from servus.state import RunState
from servus.workflow import load_workflow
from servus.config import CONFIG
from servus.core import trigger_validator

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

def run_onboarding(user_profile):
    """Helper to trigger the Onboarding Workflow"""
    try:
        logger.info(f"🚀 Triggering Onboarding for {user_profile.work_email}...")
        
        wf = load_workflow("servus/workflows/onboard_us.yaml")
        state = RunState()
        context = {
            "config": CONFIG,
            "user_profile": user_profile,
            "dry_run": False # Production is LIVE
        }
        
        orch = Orchestrator(wf, context, state, logger)
        orch.run(dry_run=False)
        
    except Exception as e:
        logger.error(f"❌ Failed to run onboarding: {e}")

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
                run_onboarding(user)
        else:
            logger.info("   (No validated new hires found)")
    except Exception as e:
        logger.error(f"❌ Scheduler Scan Failed: {e}")

def run_scheduler():
    logger.info("🚀 SERVUS Scheduler Started (Production Mode).")
    logger.info("   - Dual-Validation Scan: Every 5 minutes")
    
    # Schedule
    schedule.every(5).minutes.do(job_scan_dual_validation)
    
    # Run once immediately
    job_scan_dual_validation()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
