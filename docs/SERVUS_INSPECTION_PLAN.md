# SERVUS Multipoint Inspection & Review Plan

**Version:** 1.0  
**Date:** 2026-01-30  
**Status:** Ready for Review

---

## 1. Overview
This document outlines the comprehensive inspection plan to verify that SERVUS is "plumbed and wired" correctly from end-to-end. The goal is to ensure continuity across all platforms before moving to production.

## 1.1 MCP v0.2 Continuity Checks

Run these checks when validating local IDE continuity infrastructure:

- Run `npm test` in the repo root to execute the MCP integration suite against an isolated temporary database.
- `health.tools` should report the expected local toolset.
- `policy.evaluate` should block destructive operations against protected targets.
- `run.begin`/`run.step`/`run.end` should produce an append-only timeline retrievable via `run.timeline`.
- Mutating tools should reject missing or conflicting idempotency metadata (`mutation.check` can preflight this).
- `retrieval.hybrid` and `query.plan` should return citation-backed local evidence.
- `incident.open` and `incident.timeline` should preserve operational breadcrumbs for follow-up work.

## 1.2 Scheduler Manual Override Queue Checks

Run these checks when validating urgent/manual onboarding support:

- Validate queue submission helper with `python3 scripts/live_onboard_test.py --dry-run ...`.
- Confirm helper writes `HOLD` by default and only executes after explicit `READY` approval.
- Validate minimal enqueue path (`--work-email` + `--start-date`) and verify Rippling/Okta enrichment fills remaining profile fields.
- Confirm Rippling token has `workers.read` and that `GET /workers?limit=1` returns `200` before relying on email-only enrichment.
- Confirm scheduler logs the configured manual override CSV path at startup.
- Confirm `HOLD` rows are ignored and only `READY` rows are processed.
- Add a valid `READY` row to the override CSV and verify one onboarding run occurs.
- Confirm the completed row is removed from the CSV after successful onboarding.
- Add an invalid `READY` row (for example identical confirmation sources) and verify it is marked `ERROR`.
- Confirm a previously completed email/start-date is skipped and dequeued, not re-onboarded.

## 2. Architecture Review (The "Wiring")

### A. Inputs & Triggers
| Source | Mechanism | Status | Verification Step |
| :--- | :--- | :--- | :--- |
| **Rippling (New Hires)** | API Poll (Every 60m) | ✅ Wired | Check `scripts/scheduler.py` logs for "Scanning Rippling". |
| **Rippling (Departures)** | API Poll (Every 60m) | ⚠️ **Safety Mode** | Verify `pending_offboards.csv` is created instead of auto-running. |
| **Freshservice** | API Poll (Every 15m) | ✅ Wired | Create a test ticket with "Employee Onboarding - [Name]" and check logs. |
| **Manual CLI** | `python -m servus` | ✅ Wired | Run `scripts/dry_run_new_hires.py` to test CLI entry point. |

### B. The Core (Orchestrator)
| Component | Function | Status | Verification Step |
| :--- | :--- | :--- | :--- |
| **Config Loader** | AWS Secrets + .env | ✅ Hybrid | Verify `servus/config.py` loads secrets from AWS (if env var set) or local .env. |
| **State Management** | In-Memory (Per Run) | ✅ Simple | Ensure logs show correct step transitions. |
| **Workflow Engine** | YAML-based Steps | ✅ Flexible | Review `servus/workflows/onboard_us.yaml` for correct order. |

### C. Integrations (The "Limbs")

#### 1. Active Directory (Passive Validation)
*   **Role:** Passive Wait & Verify.
*   **Logic:** `ad.validate_user_exists` waits for Okta to sync user.
*   **Check:**
    *   Does it connect via WinRM (NTLM)?
    *   Does it verify Group Membership (FTE vs Contractor)?
    *   Does it verify `employeeType` attribute matches Rippling?

#### 2. Google Workspace (Customization)
*   **Role:** SCIM Wait + OU Move + Groups.
*   **Logic:** `google_gam.wait_for_user_scim` -> `move_user_ou` -> `add_groups`.
*   **Check:**
    *   **OU Mapping:** Verify FTE -> `/empType-FTE`, Contractor -> `/empType-CON`.
    *   **Safety:** Verify it NEVER moves users out of `/SuperAdmins`.
    *   **Offboarding:** Verify "Surgical" Deprovisioning (Wipe, Transfer, Rename, Suspend).

#### 3. Slack (Day 1 Hygiene)
*   **Role:** SCIM Wait + Channel Add.
*   **Logic:** `slack.add_to_channels` waits for user ID.
*   **Check:**
    *   **Suppliers:** Must be SKIPPED for default channels.
    *   **FTEs:** Added to `#all-hands`.
    *   **Offboarding:** Verify "Surgical" Deactivation via API.

#### 4. Badge Printing (Physical)
*   **Role:** Metadata Push to SQS.
*   **Logic:** `badge_queue.send_print_job` -> AWS SQS -> Windows Agent.
*   **Check:**
    *   **SQS:** Verify messages land in the queue (LocalStack or AWS).
    *   **Windows Agent:** Verify `windows_badge_agent.py` picks up the job.
    *   **Print:** Verify physical print output (Bleed, Color, Photo Masking).

---

## 3. Test Plan (The "Drill")

### Phase 1: The "Dry Run" (Safe)
1.  **Configure:** Ensure `.env` has `SERVUS_SQS_ENDPOINT_URL` set to LocalStack (or AWS dev).
2.  **Run:** `python scripts/dry_run_new_hires.py`
3.  **Inspect Logs:**
    *   [ ] Did it load the profile correctly?
    *   [ ] Did AD Validation simulate "Success"?
    *   [ ] Did Google OU logic select the correct target (e.g., `/empType-FTE`)?
    *   [ ] Did Slack logic select the correct channels?
    *   [ ] Did Badge Queue simulate sending a message?

### Phase 2: The "Trigger" Test (Scheduler)
1.  **Configure:** Set `dry_run: True` in `scripts/scheduler.py` (temporarily) or rely on the fact that it calls `run_orchestrator` which uses the CLI args (wait, scheduler calls `run_onboarding` which hardcodes `dry_run=False` currently. **Action:** Update scheduler to respect a global dry-run flag for testing).
2.  **Run:** `python scripts/scheduler.py`
3.  **Simulate Input:**
    *   **Rippling:** Hard to mock without a real user. Trust the `audit_new_hires.py` logic.
    *   **Freshservice:** Create a dummy ticket "Employee Onboarding - Test Bot".
4.  **Inspect:**
    *   [ ] Did the scheduler pick up the ticket?
    *   [ ] Did it launch the workflow?

### Phase 3: The "Offboard" Safety Test
1.  **Run:** `python scripts/scheduler.py`
2.  **Simulate Input:** (Wait for a real departure or mock the `RipplingClient.get_departures` return).
3.  **Inspect:**
    *   [ ] Did it **SKIP** the workflow?
    *   [ ] Did it write to `pending_offboards.csv`?

---

## 4. Continuity Matrix (Final Verification)

| Employee Type | AD Attribute | AD Group | Google OU | Slack Channels |
| :--- | :--- | :--- | :--- | :--- |
| **FTE** | "Full-Time" | `FTE` | `/empType-FTE` | `#all-hands`, Dept |
| **Contractor** | "Contractor" | `Contractors` | `/empType-CON` | `#contractors`, Dept |
| **Intern** | "Intern" | `Interns` | `/empType-INT` | `#interns`, Dept |
| **Supplier** | "Supplier" | `Suppliers` | `/empType-SUP` | **NONE** (Restricted) |

---

## 5. Next Steps
1.  **Run Phase 1 (Dry Run)** immediately.
2.  **Review `pending_offboards.csv`** format.
3.  **Deploy Windows Agent** to the print station and verify connectivity to SQS.
