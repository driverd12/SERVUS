import unittest
from unittest.mock import patch

from servus.integrations.rippling import RipplingClient, _response_detail


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class RipplingClientTests(unittest.TestCase):
    def test_build_profile_is_bound_method(self):
        client = RipplingClient()
        self.assertTrue(callable(getattr(client, "_build_profile", None)))

    @patch("servus.integrations.rippling.requests.get")
    def test_find_user_by_email_uses_worker_result(self, mock_get):
        client = RipplingClient()
        client.token = "test-token"
        client.headers["Authorization"] = "Bearer test-token"

        mock_get.return_value = _FakeResponse(
            status_code=200,
            payload={"results": [{"id": "worker-123"}]},
        )

        expected_profile = object()
        with patch.object(client, "_build_profile", return_value=expected_profile) as mock_build:
            result = client.find_user_by_email("kayla.durgee@boom.aero")

        self.assertIs(result, expected_profile)
        mock_build.assert_called_once_with("worker-123")

    @patch("servus.integrations.rippling.requests.get")
    def test_build_profile_falls_back_to_user_name_fields(self, mock_get):
        client = RipplingClient()
        client.token = "test-token"
        client.headers["Authorization"] = "Bearer test-token"

        worker_payload = {
            "first_name": None,
            "last_name": None,
            "preferred_first_name": None,
            "work_email": "kayla.durgee@boom.aero",
            "personal_email": "kayla.personal@example.com",
            "department": {"name": "IT"},
            "employment_type": {"label": "Salaried, full-time"},
            "title": "Engineer",
            "start_date": "2026-02-17",
            "location": {"type": "WORK", "work_location_id": "loc-1"},
            "user_id": "user-123",
        }
        user_payload = {
            "name": {
                "given_name": "Kayla",
                "family_name": "Durgee",
                "preferred_given_name": "Kayla",
            }
        }

        mock_get.side_effect = [
            _FakeResponse(status_code=200, payload=worker_payload),
            _FakeResponse(status_code=200, payload=user_payload),
        ]

        profile = client._build_profile("worker-123")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.first_name, "Kayla")
        self.assertEqual(profile.last_name, "Durgee")
        self.assertEqual(profile.preferred_first_name, "Kayla")
        self.assertEqual(profile.location, "US")

    def test_response_detail_prefers_detail_field(self):
        detail = _response_detail(_FakeResponse(payload={"detail": "scope missing"}))
        self.assertEqual(detail, "scope missing")


if __name__ == "__main__":
    unittest.main()
