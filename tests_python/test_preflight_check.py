import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from io import StringIO

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module under test
try:
    from scripts import preflight_check
except ImportError:
    import scripts.preflight_check as preflight_check

class TestPreflightCheck(unittest.TestCase):

    @patch("scripts.preflight_check.run_gam")
    def test_check_google_groups(self, mock_run_gam):
        # Mock success
        mock_run_gam.return_value = (True, "Group Info", "")
        results = preflight_check.check_google_groups()
        self.assertTrue(len(results) > 0)
        for r in results:
            self.assertIn("✅", r[1])
        
        # Mock failure
        mock_run_gam.return_value = (False, "", "Not Found")
        results = preflight_check.check_google_groups()
        for r in results:
            self.assertIn("❌", r[1])

    @patch("scripts.preflight_check.requests.post")
    def test_check_slack_scopes(self, mock_post):
        # Mock success
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "user": "test_user", "team": "test_team"}
        mock_post.return_value = mock_response
        
        with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": "fake-token"}):
            results = preflight_check.check_slack_scopes()
            self.assertIn("✅", results[0][1])
        
        # Mock failure
        mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}
        with patch.dict(preflight_check.CONFIG, {"SLACK_TOKEN": "fake-token"}):
            results = preflight_check.check_slack_scopes()
            self.assertIn("❌", results[0][1])

    @patch("scripts.preflight_check.LinearClient")
    def test_check_linear_connectivity(self, MockLinearClient):
        # Mock success
        mock_client = MockLinearClient.return_value
        mock_client.api_key = "fake-key"
        mock_client._query.return_value = {"data": {"viewer": {"id": "1", "email": "test@example.com"}}}
        
        results = preflight_check.check_linear_connectivity()
        self.assertIn("✅", results[0][1])
        
        # Mock failure (API key missing)
        mock_client.api_key = None
        results = preflight_check.check_linear_connectivity()
        self.assertIn("❌", results[0][1])

    def test_check_brivo_queue(self):
        # Mock success
        with patch.dict(preflight_check.CONFIG, {"SQS_BADGE_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"}):
            results = preflight_check.check_brivo_queue()
            self.assertIn("✅", results[0][1])
        
        # Mock missing
        with patch.dict(preflight_check.CONFIG, {}, clear=True):
             # clear=True removes all keys, so SQS_BADGE_QUEUE_URL will be missing
            results = preflight_check.check_brivo_queue()
            self.assertIn("❌", results[0][1])
        
        # Mock invalid format
        with patch.dict(preflight_check.CONFIG, {"SQS_BADGE_QUEUE_URL": "http://invalid-url"}):
            results = preflight_check.check_brivo_queue()
            self.assertIn("❌", results[0][1])

if __name__ == "__main__":
    unittest.main()
