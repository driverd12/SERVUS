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

    def notify_start(self, workflow_name, user_email, trigger_source=None, request_id=None):
        msg = (
            f"🚀 *SERVUS Started*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*"
            f"{self._format_run_context(trigger_source, request_id)}"
        )
        self.send(msg, color="#36a64f") # Green

    def notify_success(self, workflow_name, user_email, summary=None, trigger_source=None, request_id=None):
        msg = (
            f"✅ *SERVUS Success*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*"
            f"{self._format_run_context(trigger_source, request_id)}"
            "\nAll steps completed successfully."
        )
        if summary:
            msg += f"\nSummary: {summary}"
        self.send(msg, color="#36a64f") # Green

    def notify_failure(
        self,
        workflow_name,
        user_email,
        error_step,
        error_msg,
        summary=None,
        trigger_source=None,
        request_id=None,
    ):
        msg = (
            f"❌ *SERVUS Failed*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*"
            f"{self._format_run_context(trigger_source, request_id)}"
            f"\nStep: `{error_step}`\nError: `{error_msg}`"
        )
        if summary:
            msg += f"\nSummary: {summary}"
        self.send(msg, color="#ff0000") # Red

    def notify_manual_intervention(self, user_email, reason):
        msg = f"⚠️ *Manual Intervention Required*\nUser: *{user_email}*\nReason: {reason}"
        self.send(msg, color="#ffa500") # Orange

    def notify_step_start(
        self,
        workflow_name,
        user_email,
        step_id,
        step_description,
        step_index,
        step_total,
        trigger_source=None,
        request_id=None,
    ):
        msg = (
            f"🔄 *SERVUS Step Started*\nWorkflow: `{workflow_name}`\nUser: *{user_email}*"
            f"{self._format_run_context(trigger_source, request_id)}"
            f"\nStep: `{step_id}` ({step_index}/{step_total})\nDetail: {step_description}"
        )
        self.send(msg, color="#439FE0") # Blue

    def notify_step_result(
        self,
        workflow_name,
        user_email,
        step_id,
        step_index,
        step_total,
        status,
        detail=None,
        trigger_source=None,
        request_id=None,
    ):
        normalized = (status or "").strip().lower()
        if normalized == "success":
            label = "✅ *SERVUS Step Succeeded*"
            color = "#36a64f"
        elif normalized == "failed":
            label = "❌ *SERVUS Step Failed*"
            color = "#ff0000"
        else:
            label = "ℹ️ *SERVUS Step Completed*"
            color = "#439FE0"

        msg = (
            f"{label}\nWorkflow: `{workflow_name}`\nUser: *{user_email}*"
            f"{self._format_run_context(trigger_source, request_id)}"
            f"\nStep: `{step_id}` ({step_index}/{step_total})"
        )
        if detail:
            msg += f"\nDetail: {detail}"
        self.send(msg, color=color)

    def _format_run_context(self, trigger_source=None, request_id=None):
        parts = []
        if trigger_source:
            parts.append(f"\nTrigger: `{trigger_source}`")
        if request_id:
            parts.append(f"\nRequest ID: `{request_id}`")
        return "".join(parts)
