from __future__ import annotations
import argparse
import json
import uuid

from .branding import ASCII_ART, TAGLINE
from .config import load_config
from .log import setup_logger
from .models import UserProfile
from .workflow import load_workflow
from .state import RunState
from .orchestrator import Orchestrator

def main():
    print(ASCII_ART)
    print(f"[ {TAGLINE} ]\n")

    ap = argparse.ArgumentParser(prog="servus", description="SERVUS user lifecycle tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--workflow", required=True, help="Path to workflow yaml")
        sp.add_argument("--profile", required=True, help="Path to user profile JSON")
        sp.add_argument("--run-id", default=None)
        sp.add_argument("--dry-run", action="store_true")

    add_common(sub.add_parser("onboard"))
    add_common(sub.add_parser("offboard"))

    args = ap.parse_args()
    run_id = args.run_id or uuid.uuid4().hex[:12]

    logger = setup_logger(run_id)
    cfg = load_config()

    with open(args.profile, "r", encoding="utf-8") as f:
        profile = UserProfile.model_validate_json(f.read())

    wf = load_workflow(args.workflow)
    state = RunState(run_id)
    ctx = {"config": cfg, "profile": profile, "logger": logger}
    Orchestrator(wf, ctx, state, logger).run(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
