import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.orchestrator import run_orchestrator
from servus.models import UserProfile

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

    # 2. Run Workflow
    try:
        # Assuming 'onboard_us' is the workflow name in your yaml files
        results = run_orchestrator("onboard_us", context)
        
        logger.info("------------------------------------------------")
        logger.info("✅ DRY RUN COMPLETE")
        # logger.info(f"   Results: {results}") 
    except Exception as e:
        logger.error(f"❌ DRY RUN FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_simulation()
