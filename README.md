# SERVUS

```text
  _____  ______  _____  __      __  _    _   _____
 / ____||  ____||  __ \ \ \    / / | |  | | / ____|
| (___  | |__   | |__) | \ \  / /  | |  | || (___
 \___ \ |  __|  |  _  /   \ \/ /   | |  | | \___ \
 ____) || |____ | | \ \    \  /    | |__| | ____) |
|_____/ |______||_|  \_\    \/      \____/ |_____/
```

**SERVUS: Provision in. Deprovision out. No loose ends.**

SERVUS is a 24/7 onboarding + offboarding orchestration system with deterministic workflows, two-source trigger validation, idempotent retries, and safety-first destructive controls.

## What It Does

- Onboarding: validates and customizes downstream systems after SCIM baseline creation.
- Offboarding: deactivates and deprovisions accounts, transfers Google data/calendar/mail routing, and enforces protected-target blocks.
- Manual off-cycle onboarding: supports urgent queue submission with minimal CLI input.

## Safety Model

- Dual-validation required for headless onboarding/offboarding triggers (Rippling + Freshservice).
- Offboarding protected-target policy is mandatory and checked in two layers:
  - Workflow policy gate: `builtin.validate_target_email`
  - Per-action wrappers on destructive actions
- AD destructive operations are blocked for protected OU patterns (default includes Service Accounts OU).
- Scheduler offboarding execution mode:
  - `staged` (default): stage only, no destructive execution
  - `auto`: execute live only when preflight is clean and protected policy is non-empty
  - `live`: force live execution

## Quick Start

```bash
cd /Users/dan.driver/Cursor_projects/python/SERVUS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run preflight:

```bash
python3 scripts/preflight_check.py --strict
```

Run scheduler (headless listener):

```bash
python3 scripts/scheduler.py
```

## Off-Cycle Onboarding (Minimal Command)

```bash
scripts/offcycle_onboard.sh \
  --work-email "<user@boom.aero>" \
  --rippling-worker-id "<rippling-worker-id>" \
  --freshservice-ticket-id "<ticket-id-or-INC-###>" \
  --reason "Off-cycle onboarding"
```

## Recommended Docs

- Operator handoff runbook card: `docs/OPERATOR_RUNBOOK_CARD.md`
- Full operational guide: `docs/Onboarding.md`
- Inspection/test plan: `docs/SERVUS_INSPECTION_PLAN.md`
- Security notes: `docs/SECURITY.md`

## Service Packaging

- macOS `launchd` installer: `scripts/install_scheduler_launchd.sh`
- Linux `systemd` renderer: `scripts/render_scheduler_systemd.sh`
