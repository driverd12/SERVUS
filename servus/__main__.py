import argparse
import logging
import sys
import json
import os
from .config import load_config
from .state import RunState
from .orchestrator import Orchestrator
from .workflow import load_workflow
from .models import UserProfile
from .integrations import freshservice  # <--- NEW IMPORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s'
)
logger = logging.getLogger("servus")


def _resolve_effective_dry_run(command, dry_run_flag, execute_live_flag):
    if execute_live_flag and dry_run_flag:
        raise ValueError("--execute-live and --dry-run are mutually exclusive.")

    if command != "offboard":
        return bool(dry_run_flag)

    # Offboarding is safety-staged by default.
    return not bool(execute_live_flag)

def main():
    parser = argparse.ArgumentParser(description="SERVUS Identity Orchestrator")
    parser.add_argument("command", choices=["onboard", "offboard"])
    parser.add_argument("--workflow", required=True, help="Path to YAML workflow definition")
    
    # 🛠️ UPDATED: Allow EITHER --profile OR --ticket
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", help="Path to User Profile JSON")
    group.add_argument("--ticket", help="Freshservice Ticket ID to fetch data from")
    
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions")
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Required for LIVE offboarding. Without this, offboard runs in safety dry-run mode.",
    )
    
    args = parser.parse_args()
    
    # 1. Load Config
    config = load_config()
    
    # 2. Load Workflow
    try:
        wf = load_workflow(args.workflow)
    except Exception as e:
        logger.error(f"Failed to load workflow: {e}")
        sys.exit(1)

    # 3. Build User Profile (Dual Mode)
    user = None
    
    if args.profile:
        # MODE A: Local JSON File
        if not os.path.exists(args.profile):
            logger.error(f"Profile not found: {args.profile}")
            sys.exit(1)
        try:
            with open(args.profile, 'r') as f:
                raw_profile = json.load(f)
                user = UserProfile(**raw_profile)
                logger.info(f"Loaded profile from JSON: {user.email}")
        except Exception as e:
            logger.error(f"Invalid user profile JSON: {e}")
            sys.exit(1)

    elif args.ticket:
        # MODE B: Freshservice Ticket (Live Data)
        logger.info(f"🔌 Connecting to Freshservice Ticket #{args.ticket}...")
        user = freshservice.fetch_ticket_data(args.ticket)
        
        if not user:
            logger.error("❌ Failed to build profile from Ticket. Check logs above.")
            sys.exit(1)
            
        logger.info(f"✅ Successfully built profile for: {user.full_name}")
        logger.info(f"   Email: {user.email}")
        logger.info(f"   Role:  {user.title} ({user.employment_type})")
        logger.info(f"   Dept:  {user.department}")

    # 4. Initialize State
    state = RunState()

    try:
        effective_dry_run = _resolve_effective_dry_run(
            command=args.command,
            dry_run_flag=args.dry_run,
            execute_live_flag=args.execute_live,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.command == "offboard":
        if args.execute_live:
            logger.warning("🚨 Offboarding live execution enabled via --execute-live.")
        else:
            logger.warning(
                "🧯 Offboarding safety mode active. Running dry-run by default. "
                "Pass --execute-live to perform destructive actions."
            )

    # 5. Build Context
    context = {
        "config": config,
        "user_profile": user,
        "dry_run": effective_dry_run
    }
    
    print_banner()

    # 6. Run Orchestrator
    orch = Orchestrator(wf, context, state, logger)
    orch.run(dry_run=effective_dry_run)

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
