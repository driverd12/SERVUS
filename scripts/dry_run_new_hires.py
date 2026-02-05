import subprocess
import json
import os
import time
import argparse
import logging
from datetime import datetime

# Setup Logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"dry_run_new_hires_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dry_run_new_hires")

# 1. The New Hires List
TARGETS = [
    {
        "first": "Dominic", 
        "last": "Lunde", 
        "email": "dominic.lunde@boom.aero", # Corrected from probable typo 'lundge' based on name, but worth verifying
        "title": "Engineer",
        "dept": "Engineering",
        "type": "Salaried, full-time"
    },
    {
        "first": "Bowen", 
        "last": "Shryock", 
        "email": "bowen.shryock@boom.aero",
        "title": "Engineer",
        "dept": "Engineering",
        "type": "Salaried, full-time"
    },
    {
        "first": "Mark", 
        "last": "Loiseau", 
        "email": "mark.loiseau@boom.aero",
        "title": "Engineer",
        "dept": "Engineering",
        "type": "Salaried, full-time"
    }
]

WORKFLOW = "servus/workflows/onboard_us.yaml"
TEMP_PROFILE = "temp_onboard_profile.json"

def run_dry_run():
    logger.info(f"🚀 Starting Onboarding Dry Run for {len(TARGETS)} users.")
    logger.info("⚠️  DRY RUN MODE: No changes will be made.")

    for i, user in enumerate(TARGETS, 1):
        logger.info(f"[{i}/{len(TARGETS)}] Simulating: {user['first']} {user['last']} <{user['email']}>...")
        
        # 1. Create temporary profile JSON
        profile_data = {
            "first_name": user["first"],
            "last_name": user["last"],
            "work_email": user["email"],
            "department": user["dept"],
            "title": user["title"],
            "employment_type": user["type"],
            "start_date": "2026-02-02", 
            "manager": "unknown",
            # Add fields for badge printing simulation
            "preferred_first_name": user["first"],
            "profile_picture_url": "https://okta.com/placeholder.png" 
        }
        
        with open(TEMP_PROFILE, "w") as f:
            json.dump(profile_data, f)
            
        # 2. Build Command
        cmd = [
            "python3", "-m", "servus", "onboard",
            "--workflow", WORKFLOW,
            "--profile", TEMP_PROFILE,
            "--dry-run" # FORCE DRY RUN
        ]
        
        # 3. Execute SERVUS
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("   ✅ Simulation Success")
                # Log the output to file for review
                logger.info(result.stdout)
            else:
                logger.error("   ❌ Simulation Failed")
                logger.error(result.stderr)
        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            
        logger.info("-" * 40)
        time.sleep(1)

    # Cleanup
    if os.path.exists(TEMP_PROFILE):
        os.remove(TEMP_PROFILE)
    logger.info("\n🏁 Dry Run Sequence Complete.")

if __name__ == "__main__":
    run_dry_run()