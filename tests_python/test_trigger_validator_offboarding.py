import unittest
from unittest.mock import patch

from servus.core import trigger_validator
from servus.models import UserProfile


class TriggerValidatorOffboardingTests(unittest.TestCase):
    def _departure_profile(self, email, end_date="2026-02-14"):
        return UserProfile(
            first_name="Casey",
            last_name="Example",
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

    @patch("servus.core.trigger_validator.freshservice.map_ticket_ids_by_email")
    @patch("servus.core.trigger_validator.freshservice.scan_for_offboarding_tickets")
    @patch("servus.core.trigger_validator.RipplingClient.get_departures")
    def test_offboarding_requires_two_source_match(
        self,
        mock_get_departures,
        mock_scan_offboarding_tickets,
        mock_map_ticket_ids_by_email,
    ):
        mock_get_departures.return_value = [
            self._departure_profile("alex.one@boom.aero"),
            self._departure_profile("alex.two@boom.aero"),
        ]
        mock_scan_offboarding_tickets.return_value = ["401", "402"]
        mock_map_ticket_ids_by_email.return_value = {
            "alex.one@boom.aero": "401",
        }

        validated = trigger_validator.validate_and_fetch_offboarding_context(minutes_lookback=60)

        self.assertEqual(len(validated), 1)
        self.assertEqual(str(validated[0].user_profile.work_email), "alex.one@boom.aero")
        self.assertEqual(validated[0].confirmation_source_a, "rippling:offboarding:alex.one@boom.aero")
        self.assertEqual(validated[0].confirmation_source_b, "freshservice:ticket_id:401")

    @patch("servus.core.trigger_validator.freshservice.map_ticket_ids_by_email", return_value={})
    @patch("servus.core.trigger_validator.freshservice.scan_for_offboarding_tickets", return_value=["999"])
    @patch("servus.core.trigger_validator.RipplingClient.get_departures")
    def test_offboarding_returns_empty_when_no_ticket_match(
        self,
        mock_get_departures,
        _mock_scan,
        _mock_map,
    ):
        mock_get_departures.return_value = [self._departure_profile("nomatch@boom.aero")]

        validated = trigger_validator.validate_and_fetch_offboarding_context(minutes_lookback=60)

        self.assertEqual(validated, [])


if __name__ == "__main__":
    unittest.main()
