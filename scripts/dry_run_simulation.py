import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.orchestrator import Orchestrator
from servus.models import UserProfile
from servus.state import RunState
from servus.workflow import load_workflow

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("servus.dry_run")

def run_simulation():
    logger.info("🧪 STARTING FULL ORCHESTRATION DRY RUN")
    
    # 1. Mock Data
    mock_profile = UserProfile(
        first_name="Simulation",
        last_name="User",
        work_email="simulation.user@boom.aero",
        employment_type="Salaried, full-time",
        department="Engineering",
        title="Software Engineer",
        manager_email="manager@boom.aero",
        start_date=datetime.now().strftime("%Y-%m-%d")
    )
    
    context = {
        "user_profile": mock_profile,
        "dry_run": True
    }
    
    logger.info(f"   Target: {mock_profile.work_email}")
    logger.info(f"   Role: {mock_profile.employment_type}")
    logger.info("------------------------------------------------")

    # 2. Load workflow and run orchestrator in dry-run mode.
    try:
        workflow_path = os.path.join("servus", "workflows", "onboard_us.yaml")
        workflow = load_workflow(workflow_path)
        state = RunState()
        orch = Orchestrator(workflow, context, state, logger)
        result = orch.run(dry_run=True)

        logger.info("------------------------------------------------")
        logger.info("✅ DRY RUN COMPLETE (success=%s)", result.get("success"))
    except Exception as e:
        logger.error(f"❌ DRY RUN FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_simulation()
