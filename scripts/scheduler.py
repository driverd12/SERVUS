import time
import logging
import schedule
import csv
import os
from datetime import datetime
from servus.orchestrator import Orchestrator
from servus.state import RunState
from servus.workflow import load_workflow
from servus.config import CONFIG
from servus.integrations.rippling import RipplingClient
from servus.integrations import freshservice

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("servus.scheduler")

def run_onboarding(user_profile):
    """Helper to trigger the Onboarding Workflow"""
    # Check for global dry run override
    is_dry_run = os.getenv("SERVUS_SCHEDULER_DRY_RUN", "False").lower() == "true"
    
    try:
        logger.info(f"🚀 Triggering Onboarding for {user_profile.email} (Dry Run: {is_dry_run})...")
        
        wf = load_workflow("servus/workflows/onboard_us.yaml")
        state = RunState()
        context = {
            "config": CONFIG,
            "user_profile": user_profile,
            "dry_run": is_dry_run
        }
        
        orch = Orchestrator(wf, context, state, logger)
        orch.run(dry_run=is_dry_run)
        
    except Exception as e:
        logger.error(f"❌ Failed to run onboarding: {e}")

def run_offboarding(user_profile):
    """Helper to trigger the Offboarding Workflow"""
    # Check for global dry run override
    is_dry_run = os.getenv("SERVUS_SCHEDULER_DRY_RUN", "False").lower() == "true"

    try:
        logger.info(f"🚀 Triggering Offboarding for {user_profile.email} (Dry Run: {is_dry_run})...")
        
        wf = load_workflow("servus/workflows/offboard_us.yaml")
        state = RunState()
        context = {
            "config": CONFIG,
            "user_profile": user_profile,
            "dry_run": is_dry_run
        }
        
        orch = Orchestrator(wf, context, state, logger)
        orch.run(dry_run=is_dry_run)
        
    except Exception as e:
        logger.error(f"❌ Failed to run offboarding: {e}")

def job_scan_rippling():
    """
    Scans Rippling for Start Dates = TODAY or TOMORROW.
    Also scans for Departures = TODAY.
    """
    logger.info("⏰ Scheduler: Scanning Rippling...")
    client = RipplingClient()
    
    # 1. Check New Hires (Today)
    today = datetime.now().strftime("%Y-%m-%d")
    new_hires = client.get_new_hires(start_date=today)
    
    if new_hires:
        logger.info(f"   Found {len(new_hires)} new hires starting TODAY ({today})")
        for user in new_hires:
            run_onboarding(user)
    else:
        logger.info("   (No new hires found for today)")

    # 2. Check Departures (Today)
    departures = client.get_departures(end_date=today)
    
    if departures:
        logger.info(f"   ⚠️  Found {len(departures)} departures for TODAY ({today})")
        
        # SAFETY MODE: Report to CSV instead of running offboarding
        csv_file = "pending_offboards.csv"
        file_exists = os.path.isfile(csv_file)
        
        try:
            with open(csv_file, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Name", "Email", "Department", "Type", "End Date"])
                
                for user in departures:
                    writer.writerow([
                        datetime.now().isoformat(),
                        f"{user.first_name} {user.last_name}",
                        user.work_email,
                        user.department,
                        user.employment_type,
                        today
                    ])
                    logger.info(f"      -> Added {user.work_email} to {csv_file} (Manual Review Required)")
                    
        except Exception as e:
            logger.error(f"❌ Failed to write to CSV: {e}")
            
    else:
        logger.info("   (No departures found for today)")

def job_scan_freshservice():
    """
    Scans Freshservice for new 'Onboarding' tickets.
    """
    logger.info("⏰ Scheduler: Scanning Freshservice...")
    ticket_ids = freshservice.scan_for_onboarding_tickets(minutes_lookback=15)
    
    if ticket_ids:
        logger.info(f"   Found {len(ticket_ids)} new tickets.")
        for tid in ticket_ids:
            # Fetch full data
            user = freshservice.fetch_ticket_data(tid)
            if user:
                run_onboarding(user)
    else:
        logger.info("   (No new tickets found)")

def run_scheduler():
    logger.info("🚀 SERVUS Scheduler Started.")
    logger.info("   - Rippling Scan: Every 1 hour")
    logger.info("   - Freshservice Scan: Every 15 minutes")
    
    # Schedule
    schedule.every(60).minutes.do(job_scan_rippling)
    schedule.every(15).minutes.do(job_scan_freshservice)
    
    # Run once immediately on startup
    job_scan_rippling()
    job_scan_freshservice()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
