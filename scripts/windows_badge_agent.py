import argparse
import time
import json
import logging
import sys
import os
import random

# Add project root to path to allow imports if running from scripts/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.config import CONFIG
from servus.integrations.brivo import BrivoClient
try:
    import boto3
except ImportError:
    print("Error: boto3 is required. pip install boto3")
    sys.exit(1)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("badge_agent")

def print_badge(user_data):
    """
    Simulates the physical printing process.
    In a real scenario, this would interface with a local card printer driver
    (e.g., via win32print or a proprietary SDK).
    """
    first = user_data.get("first_name")
    last = user_data.get("last_name")
    email = user_data.get("email")
    
    logger.info(f"🖨️  PRINTING BADGE for: {first} {last} ({email})")
    logger.info("   ... Rendering Image ...")
    logger.info("   ... Sending to Printer ...")
    time.sleep(2) # Simulate print time
    logger.info("✅ PRINT COMPLETE.")

def run_test_mode():
    """
    Bypasses SQS. Creates a random test user in Brivo, then prints.
    """
    logger.info("🧪 STARTING TEST MODE")
    
    # 1. Generate Dummy Data
    rand_id = random.randint(1000, 9999)
    test_user = {
        "first_name": "Test",
        "last_name": f"BadgeUser_{rand_id}",
        "email": f"test.badge.{rand_id}@boom.aero"
    }
    
    logger.info(f"   Generated Test User: {test_user['email']}")
    
    # 2. Create in Brivo
    client = BrivoClient()
    logger.info("   Connecting to Brivo...")
    if client.create_user(test_user["first_name"], test_user["last_name"], test_user["email"]):
        logger.info("   ✅ Brivo User Created.")
    else:
        logger.error("   ❌ Failed to create Brivo user. Aborting.")
        return

    # 3. Print
    print_badge(test_user)
    logger.info("🧪 TEST MODE COMPLETE")

def run_daemon_mode():
    """
    Polls SQS for print jobs.
    """
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    region = CONFIG.get("AWS_REGION", "us-east-1")
    
    if not queue_url:
        logger.error("❌ SQS_BADGE_QUEUE_URL not set in .env")
        return

    sqs = boto3.client("sqs", region_name=region)
    logger.info(f"📡 Badge Agent Listening on {queue_url}...")

    while True:
        try:
            # Long Polling
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20
            )

            messages = response.get("Messages", [])
            for msg in messages:
                body = json.loads(msg["Body"])
                handle = msg["ReceiptHandle"]
                
                action = body.get("action")
                if action == "print_badge":
                    user_data = body.get("user", {})
                    logger.info(f"📨 Received Print Job: {user_data.get('email')}")
                    
                    # Execute Print
                    print_badge(user_data)
                    
                    # Delete Message
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=handle)
                    logger.info("🗑️  Job removed from queue.")
                else:
                    logger.warning(f"Unknown action: {action}")

        except KeyboardInterrupt:
            logger.info("🛑 Stopping Agent...")
            break
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SERVUS Windows Badge Agent")
    parser.add_argument("--test-mode", action="store_true", help="Create a test user in Brivo and print immediately (Bypasses Queue)")
    args = parser.parse_args()

    if args.test_mode:
        run_test_mode()
    else:
        run_daemon_mode()
