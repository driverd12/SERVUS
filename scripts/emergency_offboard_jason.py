import subprocess
import json
import os
import time
import logging
import sys
from datetime import datetime

# Setup Logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"emergency_offboard_jason_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("emergency_offboard")

# Target Data
TARGET = {
    "first": "Jason",
    "last": "Merret",
    "email": "jason.merret@boom.aero",
    "department": "Engineering", # Assumption, but not critical for offboarding
    "title": "Engineer",
    "employment_type": "Full-Time",
    "start_date": "2020-01-01",
    "manager": "mihalis.veletas@boom.aero"
}

TRANSFER_TARGET = "mihalis.veletas@boom.aero"
WORKFLOW = "servus/workflows/offboard_us.yaml"
TEMP_PROFILE = "temp_offboard_jason.json"

def run_emergency_offboard(dry_run=True):
    logger.info(f"🚨 STARTING EMERGENCY OFFBOARDING for {TARGET['email']}")
    logger.info(f"👉 Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"👉 Transfer Target: {TRANSFER_TARGET}")

    # 1. Create temporary profile JSON
    profile_data = {
        "first_name": TARGET["first"],
        "last_name": TARGET["last"],
        "work_email": TARGET["email"],
        "department": TARGET["department"],
        "title": TARGET["title"],
        "employment_type": TARGET["employment_type"],
        "start_date": TARGET["start_date"],
        "manager": TARGET["manager"]
    }
    
    with open(TEMP_PROFILE, "w") as f:
        json.dump(profile_data, f)
        
    # 2. Build Command
    # We need to pass the transfer target via environment variable
    env = os.environ.copy()
    env["SERVUS_OFFBOARDING_ADMIN"] = TRANSFER_TARGET
    
    cmd = [
        sys.executable, "-m", "servus", "offboard",
        "--workflow", WORKFLOW,
        "--profile", TEMP_PROFILE
    ]
    
    if dry_run:
        cmd.append("--dry-run")
        
    # 3. Execute SERVUS
    try:
        logger.info("⚡ Executing workflow...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Workflow Completed Successfully")
            logger.info("--- Output (Stdout) ---")
            logger.info(result.stdout)
            logger.info("--- Logs (Stderr) ---")
            logger.info(result.stderr)
        else:
            logger.error("❌ Workflow Failed")
            logger.error("--- Stderr ---")
            logger.error(result.stderr)
            logger.info("--- Stdout ---")
            logger.info(result.stdout)
            
    except Exception as e:
        logger.error(f"❌ Exception: {e}")
        
    # Cleanup
    if os.path.exists(TEMP_PROFILE):
        os.remove(TEMP_PROFILE)
    logger.info("\n🏁 Emergency Sequence Finished.")

if __name__ == "__main__":
    # Default to Dry Run
    run_emergency_offboard(dry_run=True)
