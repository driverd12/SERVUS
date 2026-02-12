import unittest
from unittest.mock import patch

from servus.integrations import brivo
from servus.models import UserProfile


class _DummyNotifier:
    def __init__(self):
        self.calls = []

    def notify_badge_manual_action(self, **kwargs):
        self.calls.append(kwargs)


def _context():
    return {
        "trigger_source": "manual_override_csv",
        "request_id": "REQ-123",
        "user_profile": UserProfile(
            first_name="Kayla",
            last_name="Durgee",
            work_email="kayla.durgee@boom.aero",
            personal_email=None,
            department="TechOps",
            title="Systems Engineer - Infrastructure & Support",
            manager_email="alex.mccoy@boom.aero",
            preferred_first_name="Kayla",
            profile_picture_url=None,
            employment_type="Salaried, full-time",
            start_date="2026-02-17",
            location="US",
        ),
    }


class BrivoManualFallbackTests(unittest.TestCase):
    @patch.dict(brivo.CONFIG, {"SQS_BADGE_QUEUE_URL": ""}, clear=False)
    @patch("servus.integrations.brivo._resolve_profile_image_url", return_value="https://example.com/photo.png")
    @patch("servus.integrations.brivo.SlackNotifier")
    def test_missing_queue_url_posts_manual_action(
        self,
        notifier_cls_mock,
        _resolve_image_mock,
    ):
        notifier = _DummyNotifier()
        notifier_cls_mock.return_value = notifier
        result = brivo.provision_access(_context())

        self.assertTrue(result["ok"])
        self.assertIn("manual Brivo/badge action", result["detail"])
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["user_email"], "kayla.durgee@boom.aero")
        self.assertEqual(notifier.calls[0]["profile_image_url"], "https://example.com/photo.png")

    @patch.dict(brivo.CONFIG, {"SQS_BADGE_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/test"}, clear=False)
    @patch("servus.integrations.brivo.badge_queue.send_print_job", return_value=False)
    @patch("servus.integrations.brivo._resolve_profile_image_url", return_value="https://example.com/photo.png")
    @patch("servus.integrations.brivo.SlackNotifier")
    def test_sqs_failure_posts_manual_action_and_does_not_hard_fail(
        self,
        notifier_cls_mock,
        _resolve_image_mock,
        _send_print_job_mock,
    ):
        notifier = _DummyNotifier()
        notifier_cls_mock.return_value = notifier
        result = brivo.provision_access(_context())

        self.assertTrue(result["ok"])
        self.assertIn("manual Brivo/badge action", result["detail"])
        self.assertEqual(len(notifier.calls), 1)
        self.assertIn("Failed to queue badge print job to SQS", notifier.calls[0]["reason"])


if __name__ == "__main__":
    unittest.main()
