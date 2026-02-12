import csv
import os
import tempfile
import unittest

from servus.core.manual_override_queue import (
    ERROR_STATUS,
    READY_STATUS,
    ManualOverrideRequest,
    build_onboarding_dedupe_key,
    enqueue_request,
    ensure_override_csv,
    load_ready_requests,
    mark_request_error,
    remove_request,
)
from servus.models import UserProfile


def write_rows(path, rows):
    headers = list(rows[0].keys()) if rows else [
        "request_id",
        "status",
        "work_email",
        "first_name",
        "last_name",
        "department",
        "employment_type",
        "start_date",
        "personal_email",
        "title",
        "manager_email",
        "location",
        "confirmation_source_a",
        "confirmation_source_b",
        "reason",
        "last_error",
        "created_at",
        "updated_at",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class ManualOverrideQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.temp_dir.name, "manual_overrides.csv")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ensure_override_csv_creates_file(self):
        self.assertFalse(os.path.exists(self.csv_path))
        ensure_override_csv(self.csv_path)
        self.assertTrue(os.path.exists(self.csv_path))

    def test_load_ready_requests_returns_valid_and_invalid(self):
        write_rows(
            self.csv_path,
            [
                {
                    "request_id": "REQ-1",
                    "status": READY_STATUS,
                    "work_email": "valid.user@boom.aero",
                    "first_name": "Valid",
                    "last_name": "User",
                    "department": "Engineering",
                    "employment_type": "Full-Time",
                    "start_date": "2026-02-12",
                    "personal_email": "",
                    "title": "Engineer",
                    "manager_email": "",
                    "location": "US",
                    "confirmation_source_a": "Rippling-123",
                    "confirmation_source_b": "Freshservice-456",
                    "reason": "Urgent",
                    "last_error": "",
                    "created_at": "",
                    "updated_at": "",
                },
                {
                    "request_id": "REQ-2",
                    "status": READY_STATUS,
                    "work_email": "invalid.user@boom.aero",
                    "first_name": "Invalid",
                    "last_name": "User",
                    "department": "Engineering",
                    "employment_type": "Full-Time",
                    "start_date": "",
                    "personal_email": "",
                    "title": "",
                    "manager_email": "",
                    "location": "US",
                    "confirmation_source_a": "DUPLICATE",
                    "confirmation_source_b": "DUPLICATE",
                    "reason": "",
                    "last_error": "",
                    "created_at": "",
                    "updated_at": "",
                },
                {
                    "request_id": "REQ-3",
                    "status": ERROR_STATUS,
                    "work_email": "skip.user@boom.aero",
                    "first_name": "Skip",
                    "last_name": "User",
                    "department": "Engineering",
                    "employment_type": "Full-Time",
                    "start_date": "",
                    "personal_email": "",
                    "title": "",
                    "manager_email": "",
                    "location": "US",
                    "confirmation_source_a": "A",
                    "confirmation_source_b": "B",
                    "reason": "",
                    "last_error": "",
                    "created_at": "",
                    "updated_at": "",
                },
            ],
        )

        ready, invalid = load_ready_requests(self.csv_path)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].request_id, "REQ-1")
        self.assertEqual(ready[0].user_profile.work_email, "valid.user@boom.aero")
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0][0], "REQ-2")

    def test_mark_request_error_updates_status_and_text(self):
        write_rows(
            self.csv_path,
            [
                {
                    "request_id": "REQ-4",
                    "status": READY_STATUS,
                    "work_email": "error.user@boom.aero",
                    "first_name": "Error",
                    "last_name": "User",
                    "department": "Engineering",
                    "employment_type": "Full-Time",
                    "start_date": "2026-02-20",
                    "personal_email": "",
                    "title": "",
                    "manager_email": "",
                    "location": "US",
                    "confirmation_source_a": "A",
                    "confirmation_source_b": "B",
                    "reason": "",
                    "last_error": "",
                    "created_at": "",
                    "updated_at": "",
                }
            ],
        )

        updated = mark_request_error(self.csv_path, "REQ-4", "simulated failure")
        self.assertTrue(updated)

        with open(self.csv_path, "r", newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
            self.assertEqual(row["status"], ERROR_STATUS)
            self.assertIn("simulated failure", row["last_error"])

    def test_remove_request_dequeues_row(self):
        write_rows(
            self.csv_path,
            [
                {
                    "request_id": "REQ-5",
                    "status": READY_STATUS,
                    "work_email": "remove.user@boom.aero",
                    "first_name": "Remove",
                    "last_name": "User",
                    "department": "Engineering",
                    "employment_type": "Full-Time",
                    "start_date": "2026-02-20",
                    "personal_email": "",
                    "title": "",
                    "manager_email": "",
                    "location": "US",
                    "confirmation_source_a": "A",
                    "confirmation_source_b": "B",
                    "reason": "",
                    "last_error": "",
                    "created_at": "",
                    "updated_at": "",
                }
            ],
        )

        removed = remove_request(self.csv_path, "REQ-5")
        self.assertTrue(removed)

        with open(self.csv_path, "r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [])

    def test_build_onboarding_dedupe_key_uses_email_and_start_date(self):
        user = UserProfile(
            first_name="Jane",
            last_name="Doe",
            work_email="jane.doe@boom.aero",
            personal_email=None,
            department="Engineering",
            title="Engineer",
            manager_email=None,
            employment_type="Full-Time",
            start_date="2026-02-12",
            location="US",
        )
        key = build_onboarding_dedupe_key(user)
        self.assertEqual(key, "jane.doe@boom.aero|2026-02-12")

    def test_enqueue_request_inserts_ready_row(self):
        user = UserProfile(
            first_name="Queue",
            last_name="User",
            work_email="queue.user@boom.aero",
            personal_email=None,
            department="Engineering",
            title="Engineer",
            manager_email=None,
            employment_type="Full-Time",
            start_date="2026-02-15",
            location="US",
        )
        request = ManualOverrideRequest(
            request_id="REQ-QUEUE-1",
            user_profile=user,
            confirmation_source_a="Rippling-1",
            confirmation_source_b="Freshservice-1",
            reason="Urgent onboarding",
        )
        action = enqueue_request(self.csv_path, request)
        self.assertEqual(action, "inserted")

        with open(self.csv_path, "r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["request_id"], "REQ-QUEUE-1")
            self.assertEqual(rows[0]["status"], READY_STATUS)

    def test_enqueue_request_duplicate_requires_allow_update(self):
        user = UserProfile(
            first_name="Queue",
            last_name="User",
            work_email="queue.user@boom.aero",
            personal_email=None,
            department="Engineering",
            title="Engineer",
            manager_email=None,
            employment_type="Full-Time",
            start_date="2026-02-15",
            location="US",
        )
        request = ManualOverrideRequest(
            request_id="REQ-QUEUE-2",
            user_profile=user,
            confirmation_source_a="Rippling-1",
            confirmation_source_b="Freshservice-1",
            reason="Urgent onboarding",
        )
        enqueue_request(self.csv_path, request)
        with self.assertRaises(ValueError):
            enqueue_request(self.csv_path, request)

        updated_request = ManualOverrideRequest(
            request_id="REQ-QUEUE-2",
            user_profile=user,
            confirmation_source_a="Rippling-2",
            confirmation_source_b="Freshservice-2",
            reason="Updated sources",
        )
        action = enqueue_request(self.csv_path, updated_request, allow_update=True)
        self.assertEqual(action, "updated")


if __name__ == "__main__":
    unittest.main()
