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
- If `SERVUS_SLACK_WEBHOOK_URL` is set, onboarding/offboarding should emit consolidated run-level notifications by default.
- If `SERVUS_SLACK_NOTIFICATION_MODE=verbose`, verify step-level notifications are emitted.

## 1.2 Scheduler Manual Override Queue Checks

Run these checks when validating urgent/manual onboarding support:

- Start scheduler once and confirm startup preflight reports any blocking action wiring/config issues before first scan.
- Run `python3 scripts/preflight_check.py --strict` and confirm Slack scope validation catches missing `users:read.email` or invite-write scopes before live runs.
- Validate queue submission helper with `python3 scripts/live_onboard_test.py --dry-run ...`.
- Validate simplified wrapper with `scripts/offcycle_onboard.sh --help` and one non-production queue submission.
- Confirm helper writes `HOLD` by default and only executes after explicit `READY` approval.
- Validate minimal enqueue path (`--work-email` + `--start-date`) and verify Rippling/Okta enrichment fills remaining profile fields.
- Confirm Google policy defaults are correct for employment types (`team@boom.aero` for FTE, `contractors@boom.aero` for non-FTE, plus intern/supplier add-ons).
- Confirm Rippling token has `workers.read` and that `GET /workers?limit=1` returns `200` before relying on email-only enrichment.
- Confirm scheduler logs the configured manual override CSV path at startup.
- Validate service packaging scripts:
  - `scripts/install_scheduler_launchd.sh --dry-run`
  - `scripts/render_scheduler_systemd.sh --output ./servus-scheduler.service`
- Confirm `servus/data/google_groups.yaml` and `servus/data/slack_channels.yaml` reflect intended production targets before enabling live onboarding.
- Confirm `HOLD` rows are ignored and only `READY` rows are processed.
- Add a `READY` row with future `start_date` and verify scheduler defers execution until eligible.
- Add the same row with `allow_before_start_date=true` and verify it executes immediately.
- Validate Brivo fallback: when SQS is unavailable and `SERVUS_BRIVO_QUEUE_REQUIRED=false`, verify workflow posts a manual Slack instruction and continues without hard-failing on badge step.
- Add a valid `READY` row to the override CSV and verify one onboarding run occurs.
- Confirm the completed row is removed from the CSV after successful onboarding.
- Add an invalid `READY` row (for example identical confirmation sources) and verify it is marked `ERROR`.
- Confirm a previously completed email/start-date is skipped and dequeued, not re-onboarded.

## 1.3 Offboarding Automation Checks

Run these checks when validating headless offboarding reliability:

- Confirm scheduler startup logs both modes and paths:
  - pending offboarding CSV path.
  - offboarding execution mode (`STAGED`, `AUTO`, or `LIVE`).
- Confirm protected-target policy is loaded and non-empty before enabling live destructive runs:
  - policy file path (`SERVUS_PROTECTED_TARGETS_FILE` or default `servus/data/protected_targets.yaml`).
  - merged policy counts in `python3 scripts/preflight_check.py`.
  - includes both protected emails and protected usernames (for local-part identities such as admin service users).
- Confirm offboarding workflow contains the mandatory policy gate step:
  - `builtin.validate_target_email` must execute before destructive actions.
- Confirm offboarding workflow contains manager routing gate:
  - `okta.verify_manager_resolved` must execute before destructive actions.
- Validate dual-source match path for departures:
  - Rippling departure candidate with matching Freshservice offboarding ticket should be accepted.
  - Rippling-only departure should be logged as mismatch and skipped.
- With `SERVUS_OFFBOARDING_EXECUTION_ENABLED=false`, confirm validated departures are staged into `servus_state/pending_offboards.csv` and no destructive workflow executes.
- With `SERVUS_OFFBOARDING_EXECUTION_ENABLED=true`, confirm validated departures execute offboarding workflow and are removed from pending CSV on success.
- With `SERVUS_OFFBOARDING_EXECUTION_MODE=auto`, confirm validated departures execute only when preflight has no blocking issues and protected-target policy is non-empty.
- Confirm failed live offboarding runs mark pending rows `ERROR` with actionable `last_error`.
- Confirm reruns do not duplicate successful offboarding for the same `work_email + end_date` key.
- Confirm CLI offboarding defaults to safety dry-run unless `--execute-live` is provided.
- Confirm protected targets are blocked in both places:
  - workflow policy gate blocks the run before destructive steps.
  - per-action wrappers still block if workflow is invoked without the policy gate.
- Confirm AD-specific protected OU blocks are active for destructive AD actions:
  - default pattern `OU=Service Accounts,OU=Boom Users` blocks disable/move.
  - override pattern list via `SERVUS_PROTECTED_AD_OU_PATTERNS` as needed.
- Confirm transfer routing behavior:
  - manager email is resolved before Google deprovision.
  - Drive, Calendar, and alias routing target the resolved manager email.

## 2. Architecture Review (The "Wiring")

### A. Inputs & Triggers
| Source | Mechanism | Status | Verification Step |
| :--- | :--- | :--- | :--- |
| **Rippling (New Hires)** | API Poll (Every 60m) | ✅ Wired | Check `scripts/scheduler.py` logs for "Scanning Rippling". |
| **Rippling (Departures)** | API Poll (Every 60m) | ✅ Wired (Staged Default) | Verify dual-validation match and pending CSV staging, then enable live mode explicitly for destructive execution. |
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
1.  **Configure:** Run scheduler in normal mode and keep offboarding safety defaults (`SERVUS_OFFBOARDING_EXECUTION_ENABLED=false`) for destructive-risk isolation.
2.  **Run:** `python scripts/scheduler.py`
3.  **Simulate Input:**
    *   **Onboarding:** Create matching Rippling + Freshservice onboarding evidence.
    *   **Offboarding:** Create matching Rippling departure + Freshservice offboarding evidence.
4.  **Inspect:**
    *   [ ] Did onboarding dual-validation launch exactly one onboarding workflow?
    *   [ ] Did offboarding dual-validation stage a pending row (safety mode)?

### Phase 3: The "Offboard" Safety Test
1.  **Run:** `python scripts/scheduler.py`
2.  **Simulate Input:** (Wait for a real departure or mock the `RipplingClient.get_departures` return).
3.  **Inspect:**
    *   [ ] With `SERVUS_OFFBOARDING_EXECUTION_ENABLED=false`, did it stage in `pending_offboards.csv` and skip destructive workflow?
    *   [ ] With `SERVUS_OFFBOARDING_EXECUTION_ENABLED=true`, did it run offboarding and remove the pending row on success?
    *   [ ] On offboarding failure, did the pending row move to `ERROR` with `last_error`?

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
