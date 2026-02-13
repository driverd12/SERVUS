import unittest

from servus.__main__ import _resolve_effective_dry_run


class CliSafetyDefaultsTests(unittest.TestCase):
    def test_onboard_defaults_to_live(self):
        self.assertFalse(_resolve_effective_dry_run("onboard", dry_run_flag=False, execute_live_flag=False))

    def test_onboard_honors_dry_run(self):
        self.assertTrue(_resolve_effective_dry_run("onboard", dry_run_flag=True, execute_live_flag=False))

    def test_offboard_defaults_to_dry_run(self):
        self.assertTrue(_resolve_effective_dry_run("offboard", dry_run_flag=False, execute_live_flag=False))

    def test_offboard_execute_live_requires_flag(self):
        self.assertFalse(_resolve_effective_dry_run("offboard", dry_run_flag=False, execute_live_flag=True))

    def test_execute_live_and_dry_run_conflict(self):
        with self.assertRaises(ValueError):
            _resolve_effective_dry_run("offboard", dry_run_flag=True, execute_live_flag=True)


if __name__ == "__main__":
    unittest.main()
