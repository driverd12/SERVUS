import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from servus.core.trigger_validator import ValidatedTrigger
from servus.models import UserProfile


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scheduler.py"
SPEC = importlib.util.spec_from_file_location("scheduler", SCRIPT_PATH)
scheduler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(scheduler)


def _validated_departure(email="offboard.test@boom.aero", end_date="2026-02-14", ticket_id="140"):
    user = UserProfile(
        first_name="Off",
        last_name="Board",
        work_email=email,
        personal_email=None,
        department="IT",
        title="Engineer",
        manager_email="manager@boom.aero",
        employment_type="Salaried, full-time",
        start_date="2020-01-01",
        end_date=end_date,
        location="US",
    )
    return ValidatedTrigger(
        user_profile=user,
        confirmation_source_a=f"rippling:offboarding:{email}",
        confirmation_source_b=f"freshservice:ticket_id:{ticket_id}",
    )


class SchedulerOffboardingTests(unittest.TestCase):
    def _read_rows(self, csv_path):
        with open(csv_path, "r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_staged_mode_queues_pending_offboarding_without_execution(self):
        validated = _validated_departure(email="staged.user@boom.aero", ticket_id="140")

        with tempfile.TemporaryDirectory() as temp_dir:
            pending_csv = str(Path(temp_dir) / "pending_offboards.csv")
            with patch.object(scheduler, "PENDING_OFFBOARD_CSV_PATH", pending_csv), patch.dict(
                scheduler.CONFIG,
                {"OFFBOARDING_EXECUTION_ENABLED": False},
                clear=False,
            ), patch.object(
                scheduler.trigger_validator,
                "validate_and_fetch_offboarding_context",
                return_value=[validated],
            ), patch.object(
                scheduler,
                "run_offboarding",
                return_value=True,
            ) as run_offboarding_mock:
                scheduler._process_validated_offboarding()

            rows = self._read_rows(pending_csv)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "PENDING")
            self.assertEqual(rows[0]["work_email"], "staged.user@boom.aero")
            run_offboarding_mock.assert_not_called()

    def test_live_mode_executes_offboarding_and_clears_pending_row(self):
        validated = _validated_departure(email="live.user@boom.aero", ticket_id="141")

        with tempfile.TemporaryDirectory() as temp_dir:
            pending_csv = str(Path(temp_dir) / "pending_offboards.csv")
            with patch.object(scheduler, "PENDING_OFFBOARD_CSV_PATH", pending_csv), patch.dict(
                scheduler.CONFIG,
                {"OFFBOARDING_EXECUTION_ENABLED": True},
                clear=False,
            ), patch.object(
                scheduler.trigger_validator,
                "validate_and_fetch_offboarding_context",
                return_value=[validated],
            ), patch.object(
                scheduler,
                "run_offboarding",
                return_value=True,
            ) as run_offboarding_mock:
                scheduler._process_validated_offboarding()

            rows = self._read_rows(pending_csv)
            self.assertEqual(rows, [])
            run_offboarding_mock.assert_called_once()

    def test_auto_mode_executes_when_preflight_clean(self):
        validated = _validated_departure(email="auto.user@boom.aero", ticket_id="142")

        with tempfile.TemporaryDirectory() as temp_dir:
            pending_csv = str(Path(temp_dir) / "pending_offboards.csv")
            with patch.object(scheduler, "PENDING_OFFBOARD_CSV_PATH", pending_csv), patch.dict(
                scheduler.CONFIG,
                {"OFFBOARDING_EXECUTION_MODE": "auto"},
                clear=False,
            ), patch.object(
                scheduler.trigger_validator,
                "validate_and_fetch_offboarding_context",
                return_value=[validated],
            ), patch.object(
                scheduler,
                "run_startup_preflight",
                return_value={"blocking": [], "warnings": []},
            ), patch.object(
                scheduler,
                "protected_policy_summary",
                return_value={"total_rules": 2},
            ), patch.object(
                scheduler,
                "run_offboarding",
                return_value=True,
            ) as run_offboarding_mock:
                scheduler._process_validated_offboarding()

            rows = self._read_rows(pending_csv)
            self.assertEqual(rows, [])
            run_offboarding_mock.assert_called_once()

    def test_auto_mode_stages_when_preflight_blocking(self):
        validated = _validated_departure(email="auto.blocked@boom.aero", ticket_id="143")

        with tempfile.TemporaryDirectory() as temp_dir:
            pending_csv = str(Path(temp_dir) / "pending_offboards.csv")
            with patch.object(scheduler, "PENDING_OFFBOARD_CSV_PATH", pending_csv), patch.dict(
                scheduler.CONFIG,
                {"OFFBOARDING_EXECUTION_MODE": "auto"},
                clear=False,
            ), patch.object(
                scheduler.trigger_validator,
                "validate_and_fetch_offboarding_context",
                return_value=[validated],
            ), patch.object(
                scheduler,
                "run_startup_preflight",
                return_value={"blocking": ["missing-okta-token"], "warnings": []},
            ), patch.object(
                scheduler,
                "run_offboarding",
                return_value=True,
            ) as run_offboarding_mock:
                scheduler._process_validated_offboarding()

            rows = self._read_rows(pending_csv)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "PENDING")
            run_offboarding_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
