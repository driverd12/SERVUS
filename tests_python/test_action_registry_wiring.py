import unittest
from unittest.mock import patch

from servus import actions


class ActionRegistryWiringTests(unittest.TestCase):
    def test_registry_includes_hardening_actions(self):
        self.assertIn("google_gam.wait_for_user_scim", actions.ACTIONS)
        self.assertIn("apple.check_device_assignment", actions.ACTIONS)
        self.assertIn("brivo.provision_access", actions.ACTIONS)
        self.assertIn("okta.deactivate_user", actions.ACTIONS)
        self.assertIn("ad.verify_user_disabled", actions.ACTIONS)
        self.assertIn("slack.deactivate_user", actions.ACTIONS)
        self.assertIn("google_gam.deprovision_user", actions.ACTIONS)

    def test_apple_wrapper_skips_when_no_serial_number(self):
        result = actions.ACTIONS["apple.check_device_assignment"](
            {"user_profile": {"work_email": "kayla.durgee@boom.aero"}}
        )
        self.assertIsInstance(result, dict)
        self.assertTrue(result["ok"])
        self.assertIn("No device serial provided", result["detail"])

    @patch("servus.actions.apple.check_device_assignment", return_value={"ok": True, "detail": "Found."})
    def test_apple_wrapper_passes_serial_to_integration(self, apple_check_mock):
        result = actions.ACTIONS["apple.check_device_assignment"](
            {"device_serial_number": "C02ABC123XYZ"}
        )
        apple_check_mock.assert_called_once_with("C02ABC123XYZ")
        self.assertEqual(result, {"ok": True, "detail": "Found."})


if __name__ == "__main__":
    unittest.main()
