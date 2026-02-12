import logging
import unittest
from unittest.mock import patch

from servus.orchestrator import Orchestrator
from servus.state import RunState
from servus.workflow import Workflow, WorkflowStep


class _DummyProfile:
    work_email = "kayla.durgee@boom.aero"


class _DummyNotifier:
    def __init__(self):
        self.events = []

    def notify_start(self, *args, **kwargs):
        self.events.append(("start", args, kwargs))

    def notify_step_start(self, *args, **kwargs):
        self.events.append(("step_start", args, kwargs))

    def notify_step_result(self, *args, **kwargs):
        self.events.append(("step_result", args, kwargs))

    def notify_success(self, *args, **kwargs):
        self.events.append(("success", args, kwargs))

    def notify_failure(self, *args, **kwargs):
        self.events.append(("failure", args, kwargs))


class OrchestratorSlackNotificationsTests(unittest.TestCase):
    @patch.dict("servus.orchestrator.ACTIONS", {"test.ok": lambda ctx: True}, clear=False)
    def test_notifies_step_lifecycle_and_success_summary(self):
        wf = Workflow(
            name="Test Workflow",
            description="Test",
            steps=[
                WorkflowStep(
                    id="step_ok",
                    description="Run a passing action",
                    type="action",
                    action="test.ok",
                )
            ],
        )
        context = {
            "user_profile": _DummyProfile(),
            "trigger_source": "manual_override_csv",
            "request_id": "REQ-123",
        }
        orch = Orchestrator(wf, context, RunState(), logging.getLogger("test.orch"))
        notifier = _DummyNotifier()
        orch.notifier = notifier

        result = orch.run(dry_run=False)
        self.assertTrue(result["success"])

        event_types = [event[0] for event in notifier.events]
        self.assertIn("start", event_types)
        self.assertIn("step_start", event_types)
        self.assertIn("step_result", event_types)
        self.assertIn("success", event_types)

        success_events = [e for e in notifier.events if e[0] == "success"]
        self.assertEqual(len(success_events), 1)
        _, _, kwargs = success_events[0]
        summary = kwargs.get("summary", "")
        self.assertIn("steps_total=1", summary)
        self.assertIn("steps_succeeded=1", summary)
        self.assertIn("steps_failed=0", summary)


if __name__ == "__main__":
    unittest.main()
