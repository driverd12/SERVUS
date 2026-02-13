import unittest
from unittest.mock import patch

from servus.integrations import google_gam, slack
from servus.models import UserProfile


class DryRunIsolationTests(unittest.TestCase):
    def _profile(self):
        return UserProfile(
            first_name="Casey",
            last_name="Tester",
            work_email="casey.tester@boom.aero",
            personal_email=None,
            department="Engineering",
            title="Engineer",
            manager_email="manager@boom.aero",
            employment_type="Salaried, full-time",
            start_date="2026-02-17",
            location="US",
        )

    @patch("servus.integrations.google_gam.run_gam")
    def test_google_wait_scim_dry_run_skips_gam_calls(self, run_gam_mock):
        result = google_gam.wait_for_user_scim({"user_profile": self._profile(), "dry_run": True})
        self.assertTrue(result["ok"])
        run_gam_mock.assert_not_called()

    @patch("servus.integrations.google_gam.run_gam")
    def test_google_move_ou_dry_run_skips_gam_calls(self, run_gam_mock):
        result = google_gam.move_user_ou({"user_profile": self._profile(), "dry_run": True})
        self.assertTrue(result["ok"])
        run_gam_mock.assert_not_called()

    @patch("servus.integrations.google_gam.run_gam")
    def test_google_deprovision_dry_run_skips_gam_calls(self, run_gam_mock):
        result = google_gam.deprovision_user({"user_profile": self._profile(), "dry_run": True})
        self.assertTrue(result)
        run_gam_mock.assert_not_called()

    @patch("servus.integrations.slack._lookup_user_by_email")
    @patch("servus.integrations.slack._load_channel_policy")
    def test_slack_add_channels_dry_run_skips_lookup(self, load_policy_mock, lookup_mock):
        load_policy_mock.return_value = {"global": ["C123"], "departments": {}, "employment_type": {}}
        result = slack.add_to_channels({"user_profile": self._profile(), "dry_run": True})
        self.assertTrue(result["ok"])
        lookup_mock.assert_not_called()

    @patch("servus.integrations.slack._lookup_user_by_email")
    def test_slack_deactivate_dry_run_skips_lookup(self, lookup_mock):
        result = slack.deactivate_user({"user_profile": self._profile(), "dry_run": True})
        self.assertTrue(result)
        lookup_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
