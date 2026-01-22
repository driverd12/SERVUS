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

SERVUS is a workflow-driven user lifecycle tool (onboarding now, offboarding next) designed to run headless on EC2/VM/container.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with real secrets (do not commit)
python -m servus onboard --workflow servus/workflows/onboard_us.yaml --profile examples/user_profile.json --dry-run
```

## Workflows
Workflows live in `servus/workflows/`. Each step can define:
- `action`: what to do (e.g. `ad.provision_user`, `okta.assign_apps`, `builtin.manual`)
- `verify`: how to confirm it worked
- `requires`: dependencies
- `retries`: retry policy

## Secrets
Secrets load from environment variables (optionally via `.env`). We do **not** embed AD/Okta secrets in source.

If you still have the legacy script with embedded values, generate a `.env` locally:
```bash
python scripts/extract_legacy_secrets.py /path/to/provision_user.py > .env
```

## Source artifacts
- `docs/Onboarding.md` (best practices)
- `docs/onboarding_template_master.csv` (checklist master)
