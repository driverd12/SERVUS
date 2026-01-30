import time
import logging
import schedule
from servus.orchestrator import run_orchestrator
from servus.config import CONFIG

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("servus.scheduler")

def job():
    """
    The main job that runs the orchestration.
    In a real scenario, this might fetch pending hires from a DB or API.
    For now, it runs a check.
    """
    logger.info("⏰ Scheduler: Triggering Onboarding Workflow...")
    
    # Example: In a real app, you'd fetch the payload from a source.
    # Here we might just run a check or health ping if no payload is provided.
    # Or, if we are polling Rippling API for changes:
    
    # context = fetch_pending_hires()
    # if context:
    #     run_orchestrator("onboard_us", context)
    
    logger.info("   (No pending hires found in this poll cycle)")

def run_scheduler():
    logger.info("🚀 SERVUS Scheduler Started.")
    
    # Schedule the job every 5 minutes
    schedule.every(5).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
