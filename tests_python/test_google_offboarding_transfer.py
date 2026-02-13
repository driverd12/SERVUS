import unittest
from unittest.mock import patch

from servus.integrations import google_gam
from servus.models import UserProfile


def _profile(manager_email=None):
    return UserProfile(
        first_name="Off",
        last_name="Board",
        work_email="off.board@boom.aero",
        personal_email=None,
        department="IT",
        title="Engineer",
        manager_email=manager_email,
        employment_type="Salaried, full-time",
        start_date="2020-01-01",
        end_date="2026-02-14",
        location="US",
    )


class GoogleOffboardingTransferTests(unittest.TestCase):
    @patch.dict(
        "servus.integrations.google_gam.CONFIG",
        {
            "OFFBOARDING_TRANSFER_FALLBACK_TO_ADMIN": False,
            "OFFBOARDING_ADMIN_EMAIL": "admin-wolverine@boom.aero",
        },
        clear=False,
    )
    @patch("servus.integrations.google_gam.run_gam")
    def test_deprovision_fails_without_manager_when_fallback_disabled(self, run_gam_mock):
        result = google_gam.deprovision_user({"user_profile": _profile(manager_email=None), "dry_run": True})
        self.assertFalse(result)
        run_gam_mock.assert_not_called()

    @patch.dict(
        "servus.integrations.google_gam.CONFIG",
        {
            "OFFBOARDING_TRANSFER_FALLBACK_TO_ADMIN": False,
            "OFFBOARDING_ADMIN_EMAIL": "admin-wolverine@boom.aero",
        },
        clear=False,
    )
    @patch("servus.integrations.google_gam.run_gam")
    def test_deprovision_uses_manager_transfer_target(self, run_gam_mock):
        result = google_gam.deprovision_user(
            {"user_profile": _profile(manager_email="alex.mccoy@boom.aero"), "dry_run": True}
        )
        self.assertTrue(result)
        run_gam_mock.assert_not_called()

    @patch.dict(
        "servus.integrations.google_gam.CONFIG",
        {
            "OFFBOARDING_TRANSFER_FALLBACK_TO_ADMIN": True,
            "OFFBOARDING_ADMIN_EMAIL": "admin-wolverine@boom.aero",
        },
        clear=False,
    )
    @patch("servus.integrations.google_gam.run_gam")
    def test_deprovision_allows_admin_fallback_when_enabled(self, run_gam_mock):
        result = google_gam.deprovision_user({"user_profile": _profile(manager_email=None), "dry_run": True})
        self.assertTrue(result)
        run_gam_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
