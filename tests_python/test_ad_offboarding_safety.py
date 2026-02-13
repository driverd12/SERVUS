import unittest
from unittest.mock import MagicMock, patch

from servus.integrations import ad
from servus.models import UserProfile


def _profile():
    return UserProfile(
        first_name="Svc",
        last_name="Account",
        work_email="service.user@boom.aero",
        personal_email=None,
        department="IT",
        title="Service Account",
        manager_email="manager@boom.aero",
        employment_type="Salaried, full-time",
        start_date="2020-01-01",
        end_date="2026-02-14",
        location="US",
    )


class AdOffboardingSafetyTests(unittest.TestCase):
    def test_default_protected_ou_pattern(self):
        with patch.dict("servus.integrations.ad.CONFIG", {"PROTECTED_AD_OU_PATTERNS": ""}, clear=False):
            patterns = ad._protected_ou_patterns()
        self.assertIn("OU=Service Accounts,OU=Boom Users", patterns)

    def test_protected_ou_patterns_support_semicolon_delimiter(self):
        with patch.dict(
            "servus.integrations.ad.CONFIG",
            {"PROTECTED_AD_OU_PATTERNS": "OU=Service Accounts,OU=Boom Users;OU=Domain Controllers"},
            clear=False,
        ):
            patterns = ad._protected_ou_patterns()
        self.assertEqual(
            patterns,
            ["OU=Service Accounts,OU=Boom Users", "OU=Domain Controllers"],
        )

    @patch("servus.integrations.ad.get_session")
    def test_ensure_user_disabled_aborts_for_protected_ou(self, get_session_mock):
        session = MagicMock()
        result = MagicMock()
        result.status_code = 0
        result.std_out = b"PROTECTED_OU\n"
        result.std_err = b""
        session.run_ps.return_value = result
        get_session_mock.return_value = session

        context = {"user_profile": _profile(), "dry_run": False}
        ok = ad.ensure_user_disabled(context)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
