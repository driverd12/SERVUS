import importlib.util
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from servus.core.manual_override_queue import ManualOverrideRequest
from servus.models import UserProfile


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scheduler.py"
SPEC = importlib.util.spec_from_file_location("scheduler", SCRIPT_PATH)
scheduler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(scheduler)


class _Step:
    def __init__(self, step_id, action):
        self.id = step_id
        self.type = "action"
        self.action = action


class _Workflow:
    def __init__(self, steps, name="workflow"):
        self.name = name
        self.steps = steps


def _request(start_date_value, allow_before_start_date=False):
    user = UserProfile(
        first_name="Kayla",
        last_name="Durgee",
        work_email="kayla.durgee@boom.aero",
        personal_email=None,
        department="TechOps",
        title="Systems Engineer",
        manager_email="alex.mccoy@boom.aero",
        employment_type="Salaried, full-time",
        start_date=start_date_value,
        location="US",
    )
    return ManualOverrideRequest(
        request_id="REQ-TEST-1",
        user_profile=user,
        confirmation_source_a="rippling:worker_id:697924b36aa907afbec5b964",
        confirmation_source_b="freshservice:ticket_id:140",
        allow_before_start_date=allow_before_start_date,
    )


class SchedulerHardeningTests(unittest.TestCase):
    @patch.dict(
        scheduler.CONFIG,
        {
            "MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL": False,
            "MANUAL_OVERRIDE_ENFORCE_START_DATE": True,
        },
        clear=False,
    )
    def test_manual_guard_defers_future_start_date(self):
        request = _request("2026-02-17")
        ready, reason, invalid = scheduler._manual_request_ready_for_execution(
            request,
            today=date(2026, 2, 12),
        )
        self.assertFalse(ready)
        self.assertFalse(invalid)
        self.assertIn("Deferred until start_date=2026-02-17", reason)

    @patch.dict(
        scheduler.CONFIG,
        {
            "MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL": False,
            "MANUAL_OVERRIDE_ENFORCE_START_DATE": True,
        },
        clear=False,
    )
    def test_manual_guard_allows_request_level_urgent_override(self):
        request = _request("2026-02-17", allow_before_start_date=True)
        ready, reason, invalid = scheduler._manual_request_ready_for_execution(
            request,
            today=date(2026, 2, 12),
        )
        self.assertTrue(ready)
        self.assertFalse(invalid)
        self.assertIn("Request-level early-execution override enabled.", reason)

    @patch.dict(
        scheduler.CONFIG,
        {
            "MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL": True,
            "MANUAL_OVERRIDE_ENFORCE_START_DATE": True,
        },
        clear=False,
    )
    def test_manual_guard_allows_global_urgent_override(self):
        request = _request("2026-02-17", allow_before_start_date=False)
        ready, reason, invalid = scheduler._manual_request_ready_for_execution(
            request,
            today=date(2026, 2, 12),
        )
        self.assertTrue(ready)
        self.assertFalse(invalid)
        self.assertIn("Global early-execution override enabled.", reason)

    @patch.dict(
        scheduler.CONFIG,
        {
            "MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL": False,
            "MANUAL_OVERRIDE_ENFORCE_START_DATE": True,
        },
        clear=False,
    )
    def test_manual_guard_marks_invalid_start_date(self):
        request = _request("02/17/2026")
        ready, reason, invalid = scheduler._manual_request_ready_for_execution(
            request,
            today=date(2026, 2, 12),
        )
        self.assertFalse(ready)
        self.assertTrue(invalid)
        self.assertIn("Invalid start_date format", reason)

    @patch.object(scheduler, "_workflow_paths_for_preflight", return_value=["onboard.yaml"])
    @patch.object(scheduler, "load_workflow", return_value=_Workflow([_Step("step-1", "unknown.action")]))
    @patch.object(scheduler.os.path, "exists", return_value=True)
    def test_preflight_reports_missing_action_registry_wiring(
        self,
        _exists_mock,
        _load_workflow_mock,
        _workflow_paths_mock,
    ):
        with patch.dict(
            scheduler.CONFIG,
            {
                "OKTA_DOMAIN": "boom.okta.com",
                "OKTA_TOKEN": "token",
                "AD_HOST": "dc.boom.local",
                "AD_USER": "svc-account",
                "AD_PASS": "redacted",
                "SLACK_TOKEN": "xoxb-test",
                "GAM_PATH": "/usr/local/bin/gam",
            },
            clear=True,
        ):
            result = scheduler.run_startup_preflight()

        self.assertTrue(result["blocking"])
        self.assertIn("unknown.action", result["blocking"][0])

    @patch.object(
        scheduler,
        "_workflow_paths_for_preflight",
        return_value=["onboard.yaml"],
    )
    @patch.object(
        scheduler,
        "load_workflow",
        return_value=_Workflow([_Step("step-1", "builtin.validate_profile")]),
    )
    @patch.object(scheduler.os.path, "exists", return_value=True)
    def test_preflight_reports_missing_core_config(
        self,
        _exists_mock,
        _load_workflow_mock,
        _workflow_paths_mock,
    ):
        with patch.dict(
            scheduler.CONFIG,
            {
                "OKTA_DOMAIN": "boom.okta.com",
                "OKTA_TOKEN": "token",
                "AD_HOST": "dc.boom.local",
                "AD_USER": "svc-account",
                "AD_PASS": "",
                "SLACK_TOKEN": "xoxb-test",
                "GAM_PATH": "/usr/local/bin/gam",
            },
            clear=True,
        ):
            result = scheduler.run_startup_preflight()

        combined = " ".join(result["blocking"])
        self.assertIn("AD_PASS missing", combined)

    @patch.object(
        scheduler,
        "_workflow_paths_for_preflight",
        return_value=["offboard.yaml"],
    )
    @patch.object(
        scheduler,
        "load_workflow",
        return_value=_Workflow(
            [_Step("okta_kill", "okta.deactivate_user")],
            name="SERVUS Supplier Offboarding",
        ),
    )
    @patch.object(scheduler.os.path, "exists", return_value=True)
    @patch.object(
        scheduler,
        "protected_policy_summary",
        return_value={"path": "servus/data/protected_targets.yaml", "total_rules": 1},
    )
    def test_preflight_requires_offboarding_policy_gate(
        self,
        _policy_summary_mock,
        _exists_mock,
        _load_workflow_mock,
        _workflow_paths_mock,
    ):
        with patch.dict(
            scheduler.CONFIG,
            {
                "OKTA_DOMAIN": "boom.okta.com",
                "OKTA_TOKEN": "token",
                "AD_HOST": "dc.boom.local",
                "AD_USER": "svc-account",
                "AD_PASS": "redacted",
                "SLACK_TOKEN": "xoxb-test",
                "RIPPLING_API_TOKEN": "rpkey",
                "FRESHSERVICE_DOMAIN": "boom.freshservice.com",
                "FRESHSERVICE_API_KEY": "fskey",
                "GAM_PATH": "/usr/local/bin/gam",
            },
            clear=True,
        ):
            result = scheduler.run_startup_preflight()

        combined = " ".join(result["blocking"])
        self.assertIn("builtin.validate_target_email", combined)

    @patch.object(
        scheduler,
        "_workflow_paths_for_preflight",
        return_value=["offboard.yaml"],
    )
    @patch.object(
        scheduler,
        "load_workflow",
        return_value=_Workflow(
            [_Step("policy_gate", "builtin.validate_target_email")],
            name="SERVUS Supplier Offboarding",
        ),
    )
    @patch.object(scheduler.os.path, "exists", return_value=True)
    @patch.object(
        scheduler,
        "protected_policy_summary",
        return_value={"path": "servus/data/protected_targets.yaml", "total_rules": 1},
    )
    def test_preflight_requires_offboarding_manager_gate(
        self,
        _policy_summary_mock,
        _exists_mock,
        _load_workflow_mock,
        _workflow_paths_mock,
    ):
        with patch.dict(
            scheduler.CONFIG,
            {
                "OKTA_DOMAIN": "boom.okta.com",
                "OKTA_TOKEN": "token",
                "AD_HOST": "dc.boom.local",
                "AD_USER": "svc-account",
                "AD_PASS": "redacted",
                "SLACK_TOKEN": "xoxb-test",
                "RIPPLING_API_TOKEN": "rpkey",
                "FRESHSERVICE_DOMAIN": "boom.freshservice.com",
                "FRESHSERVICE_API_KEY": "fskey",
                "GAM_PATH": "/usr/local/bin/gam",
            },
            clear=True,
        ):
            result = scheduler.run_startup_preflight()

        combined = " ".join(result["blocking"])
        self.assertIn("okta.verify_manager_resolved", combined)


if __name__ == "__main__":
    unittest.main()
