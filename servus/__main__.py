import argparse
import logging
import sys
import json
import os
from .config import load_config
from .state import RunState  # We fixed this name in the last step
from .orchestrator import Orchestrator
from .workflow import load_workflow
from .models import UserProfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s'
)
logger = logging.getLogger("servus")

def main():
    parser = argparse.ArgumentParser(description="SERVUS Identity Orchestrator")
    parser.add_argument("command", choices=["onboard", "offboard"])
    parser.add_argument("--workflow", required=True, help="Path to YAML workflow definition")
    parser.add_argument("--profile", required=True, help="Path to User Profile JSON")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions")
    
    args = parser.parse_args()
    
    # 1. Load Config
    config = load_config()
    
    # 2. Load Workflow
    try:
        wf = load_workflow(args.workflow)
    except Exception as e:
        logger.error(f"Failed to load workflow: {e}")
        sys.exit(1)

    # 3. Load User Profile
    if not os.path.exists(args.profile):
        logger.error(f"Profile not found: {args.profile}")
        sys.exit(1)
        
    try:
        with open(args.profile, 'r') as f:
            raw_profile = json.load(f)
            # Create the Pydantic Object
            user = UserProfile(**raw_profile)
    except Exception as e:
        logger.error(f"Invalid user profile: {e}")
        sys.exit(1)

    # 4. Initialize State
    state = RunState()

    # 5. Build Context (The Dictionary)
    # This is what gets passed to every action
    context = {
        "config": config,
        "user_profile": user,  # <--- This was missing before!
        "dry_run": args.dry_run
    }
    
    print_banner()

    # 6. Run
    orch = Orchestrator(wf, context, state, logger)
    orch.run(dry_run=args.dry_run)

def print_banner():
    print(r"""
  _____  ______  _____  __      __  _    _   _____ 
 / ____||  ____||  __ \ \ \    / / | |  | | / ____|
| (___  | |__   | |__) | \ \  / /  | |  | || (___  
 \___ \ |  __|  |  _  /   \ \/ /   | |  | | \___ \ 
 ____) || |____ | | \ \    \  /    | |__| | ____) |
|_____/ |______||_|  \_\    \/      \____/ |_____/ 
    """)
    print("[ SERVUS: Provision in. Deprovision out. No loose ends. ]\n")

if __name__ == "__main__":
    main()
