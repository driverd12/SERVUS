import unittest
from unittest.mock import patch

from servus.integrations.linear import LinearClient


class LinearInviteMutationTests(unittest.TestCase):
    @patch("servus.integrations.linear.CONFIG", {"LINEAR_API_KEY": "test-key"})
    def test_invite_user_uses_organization_invite_create_mutation(self):
        client = LinearClient()
        with patch.object(
            client,
            "_query",
            return_value={
                "data": {
                    "organizationInviteCreate": {
                        "success": True,
                        "organizationInvite": {"id": "inv_123"},
                    }
                }
            },
        ) as query_mock:
            result = client.invite_user("kayla.durgee@boom.aero", "MEMBER")

        self.assertTrue(result["ok"])
        self.assertIn("Invited kayla.durgee@boom.aero", result["detail"])
        query, variables = query_mock.call_args.args
        self.assertIn("organizationInviteCreate", query)
        self.assertEqual(variables["input"]["email"], "kayla.durgee@boom.aero")
        self.assertEqual(variables["input"]["role"], "user")

    @patch("servus.integrations.linear.CONFIG", {"LINEAR_API_KEY": "test-key"})
    def test_invite_user_already_invited_is_success(self):
        client = LinearClient()
        with patch.object(
            client,
            "_query",
            return_value={"errors": [{"message": "User already invited"}]},
        ):
            result = client.invite_user("kayla.durgee@boom.aero", "guest")
        self.assertTrue(result["ok"])
        self.assertIn("already exists/invited", result["detail"])


if __name__ == "__main__":
    unittest.main()
