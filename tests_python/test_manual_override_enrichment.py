import unittest
from unittest.mock import patch

from servus.core.manual_override_enrichment import enrich_from_integrations
from servus.models import UserProfile


class ManualOverrideEnrichmentTests(unittest.TestCase):
    @patch("servus.core.manual_override_enrichment._lookup_okta_user")
    @patch("servus.core.manual_override_enrichment._lookup_rippling_profile")
    def test_enrich_combines_rippling_and_okta(self, mock_rippling, mock_okta):
        mock_rippling.return_value = UserProfile(
            first_name="Kayla",
            last_name="Durgee",
            work_email="kayla.durgee@boom.aero",
            personal_email="kayla.personal@example.com",
            department="IT",
            title="Engineer",
            manager_email="alex.mccoy@boom.aero",
            employment_type="Salaried, full-time",
            start_date="2026-02-17",
            location="US",
        )
        mock_okta.return_value = {
            "id": "00u123",
            "profile": {
                "firstName": "Kayla",
                "lastName": "Durgee",
                "manager": "alex.mccoy@boom.aero",
                "title": "Engineer",
            },
        }

        result = enrich_from_integrations("kayla.durgee@boom.aero")
        self.assertEqual(result.profile_defaults["first_name"], "Kayla")
        self.assertEqual(result.profile_defaults["department"], "IT")
        self.assertEqual(result.profile_defaults["manager_email"], "alex.mccoy@boom.aero")
        self.assertEqual(
            result.confirmation_sources,
            [
                "rippling:work_email:kayla.durgee@boom.aero",
                "okta:user:00u123",
            ],
        )

    @patch("servus.core.manual_override_enrichment._lookup_okta_user")
    @patch("servus.core.manual_override_enrichment._lookup_rippling_profile")
    def test_enrich_okta_only_still_returns_source(self, mock_rippling, mock_okta):
        mock_rippling.return_value = None
        mock_okta.return_value = {
            "id": "00u999",
            "profile": {
                "firstName": "Kayla",
                "lastName": "Durgee",
                "title": "Engineer",
                "department": "IT",
                "hrEmploymentType": "Salaried, full-time",
            },
        }

        result = enrich_from_integrations("kayla.durgee@boom.aero")
        self.assertEqual(result.profile_defaults["first_name"], "Kayla")
        self.assertEqual(result.profile_defaults["title"], "Engineer")
        self.assertEqual(result.profile_defaults["department"], "IT")
        self.assertEqual(result.profile_defaults["employment_type"], "Full-Time")
        self.assertEqual(result.confirmation_sources, ["okta:user:00u999"])

    def test_enrich_empty_email(self):
        result = enrich_from_integrations("")
        self.assertEqual(result.profile_defaults, {})
        self.assertEqual(result.confirmation_sources, [])
        self.assertEqual(result.evidence, [])


if __name__ == "__main__":
    unittest.main()
