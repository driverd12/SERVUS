import logging
import unittest
from unittest.mock import patch

from servus.orchestrator import Orchestrator
from servus.state import RunState
from servus.workflow import Workflow, WorkflowStep


class _DummyProfile:
    work_email = "kayla.durgee@boom.aero"


class _DummyNotifier:
    def __init__(self, *, step_notifications=False, start_notifications=True):
        self.events = []
        self._step_notifications = step_notifications
        self._start_notifications = start_notifications

    def allow_start_notification(self):
        return self._start_notifications

    def allow_step_notifications(self):
        return self._step_notifications

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

    def notify_run_summary(self, *args, **kwargs):
        self.events.append(("run_summary", args, kwargs))


class OrchestratorSlackNotificationsTests(unittest.TestCase):
    @patch.dict("servus.orchestrator.ACTIONS", {"test.ok": lambda ctx: True}, clear=False)
    def test_summary_mode_sends_start_and_single_run_summary(self):
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
        notifier = _DummyNotifier(step_notifications=False, start_notifications=True)
        orch.notifier = notifier

        result = orch.run(dry_run=False)
        self.assertTrue(result["success"])

        event_types = [event[0] for event in notifier.events]
        self.assertIn("start", event_types)
        self.assertNotIn("step_start", event_types)
        self.assertNotIn("step_result", event_types)
        self.assertIn("run_summary", event_types)

        success_events = [e for e in notifier.events if e[0] == "run_summary"]
        self.assertEqual(len(success_events), 1)
        _, _, kwargs = success_events[0]
        self.assertTrue(kwargs.get("success"))
        self.assertEqual(kwargs.get("step_total"), 1)
        self.assertEqual(kwargs.get("step_succeeded"), 1)
        self.assertEqual(kwargs.get("step_failed"), 0)

    @patch.dict("servus.orchestrator.ACTIONS", {"test.ok": lambda ctx: True}, clear=False)
    def test_verbose_mode_sends_step_events(self):
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
        context = {"user_profile": _DummyProfile()}
        orch = Orchestrator(wf, context, RunState(), logging.getLogger("test.orch.verbose"))
        notifier = _DummyNotifier(step_notifications=True, start_notifications=True)
        orch.notifier = notifier

        result = orch.run(dry_run=False)
        self.assertTrue(result["success"])

        event_types = [event[0] for event in notifier.events]
        self.assertIn("start", event_types)
        self.assertIn("step_start", event_types)
        self.assertIn("step_result", event_types)
        self.assertIn("run_summary", event_types)


if __name__ == "__main__":
    unittest.main()
