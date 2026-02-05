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

SERVUS is a workflow-driven identity orchestration tool designed to augment Okta SCIM. It handles the "last mile" of customization for Active Directory, Google Workspace, Slack, and Physical Access (Brivo).

## 🏗️ Architecture (Phase 2: Okta Mastered)

*   **Master of Record:** Rippling (HRIS) -> Okta.
*   **Provisioning:** Okta SCIM handles account creation for AD, Google, and Slack.
*   **SERVUS Role:**
    *   **Validation:** Verifies AD attributes and Group memberships match HRIS data.
    *   **Customization:** Moves Google OUs, adds Google Groups, and manages Slack Channels based on Employee Type (FTE vs Contractor).
    *   **Physical Access:** Queues badge print jobs to a local Windows agent via AWS SQS.

## 🚀 Quick Start

### 1. Setup
```bash
python -m venv .venv && source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your secrets (Slack Webhook, Okta Token, AD Creds, etc.)
```

### 2. Run the Scheduler (The "Listener")
The scheduler runs 24/7, polling Rippling and Freshservice for new hires.
```bash
python scripts/scheduler.py
```
*   **New Hires:** Automatically triggers the Onboarding Workflow.
*   **Departures:** Logs to `pending_offboards.csv` (Safety Mode).

### 3. Manual / Dry Run
Test the logic without making changes:
```bash
# Test specific new hires
python scripts/dry_run_new_hires.py

# Run CLI manually
python -m servus onboard --profile examples/user_profile.json --dry-run
```

## 🛠️ Components

### Workflows (`servus/workflows/`)
*   `onboard_us.yaml`: The primary sequence (Validate AD -> Wait for Google -> Customize -> Slack -> Badge).
*   `offboard_us.yaml`: The surgical deprovisioning sequence.

### Badge Printing (`scripts/windows_badge_agent.py`)
Runs on a Windows laptop connected to the ID card printer.
*   Listens to AWS SQS queue.
*   Downloads user photo and metadata.
*   Generates badge image (Front/Back) and prints immediately.

### Integrations (`servus/integrations/`)
*   `ad.py`: Passive validation via WinRM.
*   `google_gam.py`: GAM wrapper for OU/Group management.
*   `slack.py`: Channel management via API.
*   `rippling.py`: HRIS data fetching.

## 📝 Documentation
*   `docs/SERVUS_INSPECTION_PLAN.md`: Full verification checklist.
*   `docs/Onboarding.md`: Process best practices.
