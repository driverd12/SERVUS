import logging
import requests
import json
from servus.config import CONFIG

logger = logging.getLogger("servus.notifier")

class SlackNotifier:
    def __init__(self):
        self.webhook_url = CONFIG.get("SLACK_WEBHOOK_URL")
        
    def send(self, message, color="#36a64f"):
        """
        Sends a rich attachment message to Slack.
        """
        if not self.webhook_url:
            logger.debug("No SLACK_WEBHOOK_URL configured. Skipping notification.")
            return

        payload = {
            "attachments": [
                {
                    "color": color,
                    "text": message,
                    "mrkdwn_in": ["text"]
                }
            ]
        }

        try:
            response = requests.post(
                self.webhook_url, 
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            if response.status_code != 200:
                logger.warning(f"Failed to send Slack notification: {response.text}")
        except Exception as e:
            logger.warning(f"Slack notification error: {e}")

    def notify_start(self, workflow_name, user_email):
        msg = f"🚀 *SERVUS Started*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*"
        self.send(msg, color="#36a64f") # Green

    def notify_success(self, workflow_name, user_email):
        msg = f"✅ *SERVUS Success*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*\nAll steps completed successfully."
        self.send(msg, color="#36a64f") # Green

    def notify_failure(self, workflow_name, user_email, error_step, error_msg):
        msg = f"❌ *SERVUS Failed*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*\nStep: `{error_step}`\nError: `{error_msg}`"
        self.send(msg, color="#ff0000") # Red

    def notify_manual_intervention(self, user_email, reason):
        msg = f"⚠️ *Manual Intervention Required*\nUser: *{user_email}*\nReason: {reason}"
        self.send(msg, color="#ffa500") # Orange
