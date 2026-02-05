import logging
import sys
import os

# Add project root to path so we can import servus modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.notifier import SlackNotifier
from servus.config import CONFIG

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def test_notification():
    webhook_url = CONFIG.get("SLACK_WEBHOOK_URL")
    
    print("-" * 40)
    print(f"🔍 Checking Configuration...")
    if not webhook_url:
        print("❌ Error: SERVUS_SLACK_WEBHOOK_URL is missing or empty in .env")
        print("   Please add it to your .env file.")
        return
    
    # Mask the URL for security in logs
    masked_url = webhook_url[:35] + "..." + webhook_url[-5:] if len(webhook_url) > 40 else "Invalid URL"
    print(f"✅ Found Webhook URL: {masked_url}")
    print("-" * 40)

    notifier = SlackNotifier()
    
    print("🚀 Sending test message to Slack...")
    try:
        # Send a generic test message
        notifier.send(
            "👋 *Hello from SERVUS!*\nThis is a test notification to verify connectivity.", 
            color="#36a64f"
        )
        print("✅ Request sent successfully.")
        print("   👉 Check your Slack channel now!")
    except Exception as e:
        print(f"❌ Failed to send: {e}")

if __name__ == "__main__":
    test_notification()
