import argparse
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_onboard_test.py"
SPEC = importlib.util.spec_from_file_location("live_onboard_test", SCRIPT_PATH)
live_onboard_test = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(live_onboard_test)


def _args(**overrides):
    defaults = {
        "confirmation_source_a": None,
        "confirmation_source_b": None,
        "rippling_worker_id": None,
        "freshservice_ticket_id": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class LiveOnboardCliShortcutTests(unittest.TestCase):
    def test_shortcuts_generate_confirmation_sources(self):
        args = _args(
            rippling_worker_id="697924b36aa907afbec5b964",
            freshservice_ticket_id="INC-140",
        )
        sources = live_onboard_test._resolve_confirmation_sources(args, auto_sources=[])
        self.assertEqual(
            sources,
            [
                "rippling:worker_id:697924b36aa907afbec5b964",
                "freshservice:ticket_id:140",
            ],
        )

    def test_shortcuts_accept_freshservice_url(self):
        args = _args(
            rippling_worker_id="rippling:worker_id:697924b36aa907afbec5b964",
            freshservice_ticket_id="https://boom.freshservice.com/a/tickets/140?current_tab=details",
        )
        sources = live_onboard_test._resolve_confirmation_sources(args, auto_sources=[])
        self.assertEqual(
            sources,
            [
                "rippling:worker_id:697924b36aa907afbec5b964",
                "freshservice:ticket_id:140",
            ],
        )

    def test_shortcuts_require_two_distinct_sources(self):
        args = _args(rippling_worker_id="697924b36aa907afbec5b964")
        with self.assertRaises(ValueError):
            live_onboard_test._resolve_confirmation_sources(args, auto_sources=[])


if __name__ == "__main__":
    unittest.main()
