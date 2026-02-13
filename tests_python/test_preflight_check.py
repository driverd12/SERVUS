import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import preflight_check


class TestPreflightCheck(unittest.TestCase):
    @patch("scripts.preflight_check.run_gam")
    def test_check_google_groups(self, mock_run_gam):
        mock_run_gam.return_value = (True, "Group Info", "")
        results = preflight_check.check_google_groups()
        self.assertTrue(all("✅" in status for _, status in results))

        mock_run_gam.return_value = (False, "", "Not Found")
        results = preflight_check.check_google_groups()
        self.assertTrue(all("❌" in status for _, status in results))

    @patch("scripts.preflight_check.requests.post")
    def test_check_slack_scopes_success(self, mock_post):
        mock_post.return_value = MagicMock()
        mock_post.return_value.json.return_value = {"ok": True, "user": "svc", "team": "boom"}
        mock_post.return_value.headers = {
            "x-oauth-scopes": "users:read.email,conversations:write,channels:read"
        }
        mock_post.return_value.status_code = 200
        mock_targets = ["C01GENERAL"]
        with patch(
            "scripts.preflight_check._configured_slack_channel_targets",
            return_value=mock_targets,
        ):
            with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": "fake-token"}):
                results = preflight_check.check_slack_scopes()
                self.assertIn("✅", results[0][1])

    @patch("scripts.preflight_check.requests.post")
    @patch("scripts.preflight_check._configured_slack_channel_targets")
    def test_check_slack_scopes_success_with_invites_scope(self, mock_targets, mock_post):
        mock_targets.return_value = ["C01GENERAL"]
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "user": "svc", "team": "boom"}
        mock_response.headers = {
            "x-oauth-scopes": "users:read.email,channels:write.invites,channels:read"
        }
        mock_post.return_value = mock_response

        with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": "fake-token"}):
            results = preflight_check.check_slack_scopes()
            self.assertIn("✅", results[0][1])

    @patch("scripts.preflight_check.requests.post")
    @patch("scripts.preflight_check._configured_slack_channel_targets")
    def test_check_slack_scopes_missing_required_scope(self, mock_targets, mock_post):
        mock_targets.return_value = ["C01GENERAL"]
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "user": "svc", "team": "boom"}
        mock_response.headers = {"x-oauth-scopes": "conversations:write"}
        mock_post.return_value = mock_response

        with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": "fake-token"}):
            results = preflight_check.check_slack_scopes()
            self.assertIn("❌", results[0][1])
            self.assertIn("users:read.email", results[0][1])

    @patch("scripts.preflight_check.requests.post")
    @patch("scripts.preflight_check._configured_slack_channel_targets")
    def test_check_slack_scopes_missing_invite_scope(self, mock_targets, mock_post):
        mock_targets.return_value = ["C01GENERAL"]
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "user": "svc", "team": "boom"}
        mock_response.headers = {"x-oauth-scopes": "users:read.email,channels:read"}
        mock_post.return_value = mock_response

        with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": "fake-token"}):
            results = preflight_check.check_slack_scopes()
            self.assertIn("❌", results[0][1])
            self.assertIn("missing invite scope", results[0][1])

    @patch("scripts.preflight_check._configured_slack_channel_targets")
    def test_check_slack_scopes_missing_token(self, mock_targets):
        mock_targets.return_value = ["C01GENERAL"]
        with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": ""}):
            results = preflight_check.check_slack_scopes()
            self.assertIn("❌", results[0][1])

    def test_check_slack_scopes_skips_when_no_channels_configured(self):
        with patch("scripts.preflight_check._configured_slack_channel_targets", return_value=[]):
            with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": ""}):
                results = preflight_check.check_slack_scopes()
                self.assertIn("✅", results[0][1])
                self.assertIn("scope check skipped", results[0][1])

    @patch("scripts.preflight_check.LinearClient")
    def test_check_linear_connectivity_success(self, mock_linear_client):
        mock_client = mock_linear_client.return_value
        mock_client.api_key = "fake-key"
        mock_client._query.return_value = {
            "data": {"viewer": {"id": "1", "email": "test@example.com"}}
        }

        results = preflight_check.check_linear_connectivity()
        self.assertIn("✅", results[0][1])

    @patch("scripts.preflight_check.LinearClient")
    def test_check_linear_connectivity_failure(self, mock_linear_client):
        mock_client = mock_linear_client.return_value
        mock_client.api_key = "fake-key"
        mock_client._query.return_value = {"errors": [{"message": "invalid token"}]}

        results = preflight_check.check_linear_connectivity()
        self.assertIn("❌", results[0][1])

    def test_check_brivo_queue_missing(self):
        with patch.dict(
            preflight_check.CONFIG,
            {"SQS_BADGE_QUEUE_URL": "", "BRIVO_QUEUE_REQUIRED": True},
        ):
            results = preflight_check.check_brivo_queue()
            self.assertIn("❌", results[0][1])

    def test_check_brivo_queue_invalid_url(self):
        with patch.dict(
            preflight_check.CONFIG,
            {"SQS_BADGE_QUEUE_URL": "not-a-url", "BRIVO_QUEUE_REQUIRED": True},
        ):
            results = preflight_check.check_brivo_queue()
            self.assertIn("❌", results[0][1])

    @patch("scripts.preflight_check.requests.get")
    def test_check_brivo_queue_reachable(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        with patch.dict(
            preflight_check.CONFIG,
            {
                "SQS_BADGE_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
                "SQS_ENDPOINT_URL": "http://localhost:4566",
            },
        ):
            results = preflight_check.check_brivo_queue()
            self.assertIn("✅", results[0][1])
            self.assertIn("✅", results[1][1])

    @patch("scripts.preflight_check.requests.get")
    def test_check_brivo_queue_unreachable(self, mock_get):
        mock_get.side_effect = RuntimeError("connection refused")
        with patch.dict(
            preflight_check.CONFIG,
            {
                "SQS_BADGE_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
                "SQS_ENDPOINT_URL": "http://localhost:4566",
                "BRIVO_QUEUE_REQUIRED": True,
            },
        ):
            results = preflight_check.check_brivo_queue()
            self.assertIn("✅", results[0][1])
            self.assertIn("❌", results[1][1])

    @patch("scripts.preflight_check.requests.get")
    def test_check_brivo_queue_unreachable_is_warning_when_optional(self, mock_get):
        mock_get.side_effect = RuntimeError("connection refused")
        with patch.dict(
            preflight_check.CONFIG,
            {
                "SQS_BADGE_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
                "SQS_ENDPOINT_URL": "http://localhost:4566",
                "BRIVO_QUEUE_REQUIRED": False,
            },
        ):
            results = preflight_check.check_brivo_queue()
            self.assertIn("✅", results[0][1])
            self.assertIn("⚠️", results[1][1])

    def test_cli_help_runs_from_repo(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "preflight_check.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("SERVUS Integration Preflight Check", result.stdout)


if __name__ == "__main__":
    unittest.main()
