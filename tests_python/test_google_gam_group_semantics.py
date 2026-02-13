import unittest
from unittest.mock import patch
from unittest.mock import call

from servus.integrations import google_gam
from servus.models import UserProfile


def _context(employment_type="Full-Time", department="TechOps"):
    return {
        "dry_run": False,
        "user_profile": UserProfile(
            first_name="Kayla",
            last_name="Durgee",
            work_email="kayla.durgee@boom.aero",
            personal_email=None,
            department=department,
            title="Systems Engineer",
            manager_email="alex.mccoy@boom.aero",
            employment_type=employment_type,
            start_date="2026-02-17",
            location="US",
        ),
    }


class GoogleGamGroupSemanticsTests(unittest.TestCase):
    @patch("servus.integrations.google_gam.run_gam")
    def test_add_groups_fails_when_any_group_add_fails(self, run_gam_mock):
        # Full-Time + Engineering maps to two groups. One succeeds, one fails.
        run_gam_mock.side_effect = [
            (True, "", ""),
            (False, "", "Group not found"),
        ]
        result = google_gam.add_groups(_context(department="Engineering"))

        self.assertIsInstance(result, dict)
        self.assertFalse(result["ok"])
        self.assertIn("failed=1", result["detail"])
        self.assertIn("group-not-found", result["detail"])

    @patch("servus.integrations.google_gam.run_gam")
    def test_add_groups_treats_already_member_as_success(self, run_gam_mock):
        run_gam_mock.return_value = (False, "Member already exists", "")
        result = google_gam.add_groups(_context())

        self.assertIsInstance(result, dict)
        self.assertTrue(result["ok"])
        self.assertIn("already_member=1", result["detail"])
        self.assertIn("failed=0", result["detail"])

    @patch("servus.integrations.google_gam.run_gam")
    def test_add_groups_maps_supplier_to_non_fte_groups(self, run_gam_mock):
        run_gam_mock.side_effect = [
            (True, "", ""),
            (True, "", ""),
        ]
        result = google_gam.add_groups(_context(employment_type="Supplier", department="Unknown"))

        self.assertTrue(result["ok"])
        self.assertIn("group_targets=2", result["detail"])
        self.assertIn("failed=0", result["detail"])
        run_gam_mock.assert_has_calls(
            [
                call(
                    [
                        "update",
                        "group",
                        "contractors@boom.aero",
                        "add",
                        "member",
                        "kayla.durgee@boom.aero",
                    ]
                ),
                call(
                    [
                        "update",
                        "group",
                        "suppliers@boom.aero",
                        "add",
                        "member",
                        "kayla.durgee@boom.aero",
                    ]
                ),
            ]
        )


if __name__ == "__main__":
    unittest.main()
