import subprocess
import json
import os
import time
import argparse
import logging
import csv
import sys
from datetime import datetime

# Setup Logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"bulk_offboard_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bulk_offboard")

CSV_FILE = "docs/supplier_offboardings_SERVUS.csv"
WORKFLOW = "servus/workflows/offboard_us.yaml"
TEMP_PROFILE = "temp_offboard_profile.json"

def load_targets_from_csv(filepath):
    targets = []
    if not os.path.exists(filepath):
        logger.error(f"❌ CSV file not found: {filepath}")
        return []
    
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f: # utf-8-sig to handle BOM if present
            reader = csv.DictReader(f)
            for row in reader:
                # CSV headers: username,email,empType,transfer target
                # We need to parse names from email or username if not provided
                email = row.get("email", "").strip()
                if not email: continue
                
                # Guess names from email (first.last@...)
                local_part = email.split("@")[0]
                if "." in local_part:
                    first, last = local_part.split(".", 1)
                    # Remove any suffix like -LDO from last name if present in email?
                    # Actually, the username has -LDO, email usually does too based on the file.
                    # e.g. a.fedele-LDO@boom.aero
                    # Let's just use raw strings, it's for logging mostly.
                else:
                    first, last = local_part, "Unknown"

                targets.append({
                    "first": first.capitalize(),
                    "last": last.capitalize(),
                    "email": email,
                    "empType": row.get("empType", "Contractor"),
                    "transfer_target": row.get("transfer target", "admin-wolverine@boom.aero").strip()
                })
    except Exception as e:
        logger.error(f"❌ Failed to read CSV: {e}")
        return []
    
    return targets

def run_offboarding(dry_run=True, limit=None):
    mode = "DRY RUN" if dry_run else "LIVE EXECUTION"
    
    # Load Targets
    all_targets = load_targets_from_csv(CSV_FILE)
    if not all_targets:
        logger.error("No targets found. Exiting.")
        return

    logger.info(f"🚀 Starting Bulk Offboard sequence for {len(all_targets)} users.")
    logger.info(f"👉 Mode: {mode}")
    logger.info(f"👉 Input: {CSV_FILE}")
    
    if limit:
        logger.info(f"👉 Limit: Processing only first {limit} users.")
        targets_to_process = all_targets[:limit]
    else:
        targets_to_process = all_targets

    for i, user in enumerate(targets_to_process, 1):
        logger.info(f"[{i}/{len(targets_to_process)}] Processing: {user['first']} {user['last']} <{user['email']}>...")
        logger.info(f"   Transfer Target: {user['transfer_target']}")
        
        # 1. Create temporary profile JSON
        profile_data = {
            "first_name": user["first"],
            "last_name": user["last"],
            "work_email": user["email"],
            "department": "Supplier/Contractor",
            "title": "External",
            "employment_type": user["empType"], # e.g. empType-SUP
            "start_date": "2020-01-01", 
            "manager": "unknown" 
        }
        
        with open(TEMP_PROFILE, "w") as f:
            json.dump(profile_data, f)
            
        # 2. Build Command
        # Pass transfer target via ENV
        env = os.environ.copy()
        env["SERVUS_OFFBOARDING_ADMIN"] = user["transfer_target"]

        cmd = [
            sys.executable, "-m", "servus", "offboard",
            "--workflow", WORKFLOW,
            "--profile", TEMP_PROFILE
        ]
        
        if dry_run:
            cmd.append("--dry-run")
        else:
            cmd.append("--execute-live")
            
        # 3. Execute SERVUS
        try:
            # Capture both stdout and stderr
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("   ✅ Success")
                logger.info("--- Output (Stdout) ---")
                logger.info(result.stdout)
                logger.info("--- Logs (Stderr) ---")
                logger.info(result.stderr)
            else:
                logger.error("   ❌ Failed")
                logger.error("--- Stderr ---")
                logger.error(result.stderr)
                logger.info("--- Stdout ---")
                logger.info(result.stdout)

        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            
        logger.info("-" * 40)
        time.sleep(1) # Polite pause

    # Cleanup
    if os.path.exists(TEMP_PROFILE):
        os.remove(TEMP_PROFILE)
    logger.info("\n🏁 Bulk Sequence Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk Offboard Suppliers from CSV")
    parser.add_argument("--live", action="store_true", help="Run in LIVE mode (default is DRY RUN)")
    parser.add_argument("--limit", type=int, help="Limit number of users to process (e.g. 1 for testing)")
    
    args = parser.parse_args()
    
    # Default is dry_run=True, so if --live is passed, dry_run=False
    run_offboarding(dry_run=not args.live, limit=args.limit)
