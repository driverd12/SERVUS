import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from servus import actions
from servus.actions_builtin import validate_target_email
from servus.models import UserProfile
from servus.safety import evaluate_offboarding_target, protected_policy_summary
from servus.workflow import load_workflow


def _user(email="engineer@boom.aero", department="IT", title="Systems Engineer"):
    return UserProfile(
        first_name="Test",
        last_name="User",
        work_email=email,
        personal_email=None,
        department=department,
        title=title,
        manager_email="manager@boom.aero",
        employment_type="Salaried, full-time",
        start_date="2026-02-17",
        location="US",
    )


class OffboardingSafetyGuardsTests(unittest.TestCase):
    @patch.dict(
        "servus.safety.CONFIG",
        {
            "PROTECTED_TARGETS_FILE": "",
            "PROTECTED_EMAILS": "vip@boom.aero",
            "PROTECTED_DOMAINS": "",
            "PROTECTED_DEPARTMENTS": "",
            "PROTECTED_TITLES": "",
            "OFFBOARDING_ADMIN_EMAIL": "",
        },
        clear=False,
    )
    def test_evaluate_offboarding_target_blocks_protected_email(self):
        result = evaluate_offboarding_target(
            {"user_profile": _user(email="vip@boom.aero")},
            action_name="okta.deactivate_user",
        )
        self.assertFalse(result["ok"])
        self.assertIn("Protected target blocked", result["detail"])

    @patch.dict(
        "servus.safety.CONFIG",
        {
            "PROTECTED_TARGETS_FILE": "",
            "PROTECTED_EMAILS": "",
            "PROTECTED_DOMAINS": "",
            "PROTECTED_DEPARTMENTS": "",
            "PROTECTED_TITLES": "",
            "OFFBOARDING_ADMIN_EMAIL": "admin-wolverine@boom.aero",
        },
        clear=False,
    )
    def test_offboarding_admin_is_implicitly_protected(self):
        summary = protected_policy_summary()
        self.assertGreaterEqual(summary["emails"], 1)
        result = evaluate_offboarding_target(
            {"user_profile": _user(email="admin-wolverine@boom.aero")},
            action_name="google_gam.deprovision_user",
        )
        self.assertFalse(result["ok"])

    @patch.dict(
        "servus.safety.CONFIG",
        {
            "PROTECTED_TARGETS_FILE": "",
            "PROTECTED_EMAILS": "",
            "PROTECTED_USERNAMES": "danadmin",
            "PROTECTED_DOMAINS": "",
            "PROTECTED_DEPARTMENTS": "",
            "PROTECTED_TITLES": "",
            "OFFBOARDING_ADMIN_EMAIL": "",
        },
        clear=False,
    )
    def test_evaluate_offboarding_target_blocks_protected_username(self):
        result = evaluate_offboarding_target(
            {"user_profile": _user(email="danadmin@boom.aero")},
            action_name="ad.verify_user_disabled",
        )
        self.assertFalse(result["ok"])
        self.assertIn("protected username", result["detail"])

    def test_validate_target_email_blocks_external_domain(self):
        result = validate_target_email({"user_profile": _user(email="person@example.com")})
        self.assertFalse(result["ok"])
        self.assertIn("non-corporate email", result["detail"])

    def test_offboarding_guard_wrapper_blocks_underlying_action(self):
        guarded_action = actions._with_offboarding_guard("okta.deactivate_user", MagicMock(return_value=True))
        with patch("servus.actions.builtin.validate_target_email", return_value={"ok": False, "detail": "blocked"}):
            result = guarded_action({"user_profile": _user()})
        self.assertEqual(result["ok"], False)
        self.assertIn("blocked", result["detail"])

    def test_offboarding_workflow_starts_with_policy_gate(self):
        workflow_path = Path(__file__).resolve().parents[1] / "servus" / "workflows" / "offboard_us.yaml"
        workflow = load_workflow(str(workflow_path))
        self.assertGreater(len(workflow.steps), 0)
        first_step = workflow.steps[0]
        self.assertEqual(first_step.action, "builtin.validate_target_email")


if __name__ == "__main__":
    unittest.main()
