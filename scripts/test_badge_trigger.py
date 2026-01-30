import sys
import os
import logging
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.integrations import badge_queue
from servus.config import CONFIG

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_trigger")

def trigger_test_job(email="test.badge@boom.aero"):
    logger.info(f"🔫 Triggering test print job for: {email}")
    
    # Check config
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    if not queue_url:
        logger.error("❌ SQS_BADGE_QUEUE_URL is missing in .env")
        return

    user_data = {
        "first_name": "Test",
        "last_name": "TriggerUser",
        "email": email,
        "brivo_id": "12345" # Dummy ID
    }

    if badge_queue.send_print_job(user_data):
        logger.info("✅ Job sent to SQS successfully.")
        logger.info("   Now check your 'windows_badge_agent.py' terminal to see if it picks it up.")
    else:
        logger.error("❌ Failed to send job.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manually trigger a badge print job via SQS")
    parser.add_argument("--email", default="test.badge@boom.aero", help="Email to use for the test user")
    args = parser.parse_args()

    trigger_test_job(args.email)
