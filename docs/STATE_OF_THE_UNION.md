# SERVUS: State of the Union

- **Date:** 2026-02-09
- **Repo:** SERVUS
- **Mission:** Provision in. Deprovision out. No loose ends.
- **Operating Mode:** Continuous scheduler (24/7/365)

> This document is the “one page brain” for SERVUS: what it is, how it works today, what is true, what is risky, and what happens next.

---

## 1) What SERVUS Is (and is not)

### SERVUS is:
- A workflow-driven identity orchestration system that **augments** Okta SCIM with last-mile validation and customization.
- A cross-confirming listener that detects onboarding/offboarding events from **two sources** and runs the correct workflow.

### SERVUS is not:
- A replacement for Okta SCIM provisioning.
- A user-creation engine for Google/Slack/AD when those are SCIM-managed.

---

## 2) Current Architecture (SCIM-First)

### Source-of-truth flow
1. **Rippling (HRIS)** is the attribute source of truth.
2. Rippling drives **Okta** lifecycle + attributes.
3. **Okta provisions downstream platforms via SCIM** (AD, Google Workspace, Slack, etc.).
4. SERVUS is triggered by verified events and performs **post-SCIM customizations** and validation.

### SERVUS’s role by system (current intent)
- **Active Directory:** passive validation checks + offboarding disable/move (as configured).
- **Google Workspace:** wait for SCIM-created account, then move to correct OU, add groups.
- **Slack:** wait for SCIM-created account, then add to channels.
- **Physical Access / Badge:** queue badge print job to local Windows badge agent via SQS.

---

## 3) Repo Topology (for orientation)

- `scripts/scheduler.py`  
  Long-running poller/listener. Detects events and triggers workflows.
- `servus/workflows/`  
  YAML-defined workflows:
  - `onboard_us.yaml`
  - `offboard_us.yaml`
- `servus/orchestrator.py`  
  Runs workflows, handles step execution, error catching, and context.
- `servus/integrations/`  
  System adapters: `okta.py`, `rippling.py`, `freshservice.py`, `ad.py`, `google_gam.py`, `slack.py`, `brivo.py`, etc.
- `servus_state/`  
  Runtime state snapshots / checkpoints (source of truth for “what happened”, depending on implementation).
- `docs/`  
  Inspection plan, onboarding practices, templates.
- `logs/`  
  Runtime logs (do not treat as a correctness dependency).

---

## 4) Operational Posture (Safety & Reliability)

### Core invariants (must remain true)
- SCIM-first authority model.
- Two-source confirmation before action.
- Offboarding defaults to staged/log-only.
- Idempotent steps; safe restarts.
- Wait loops for SCIM lag.
- Protected targets cause hard abort.

(See `docs/ADR/0001-servus-constitution.md`.)

### Audit trail expectations
Every external call should emit structured logs including workflow, step, system, action, target, result, and errors.

---

## 5) Current Workflows (High-level)

### Onboarding (`onboard_us.yaml`) intent
Typical flow:
1. Validate input profile
2. Confirm downstream user exists (AD / Google / Slack) after SCIM
3. Apply customizations:
   - Google OU placement + groups
   - Slack channel membership
   - Device/badge related steps (as configured)

### Offboarding (`offboard_us.yaml`) intent
- Staged by default.
- Should:
  - Disable/suspend where appropriate
  - Move to “disabled” containers (AD) if configured
  - Remove access carefully and safely
  - Preserve evidence and avoid deleting protected targets

---

## 6) Known Risks & Landmines

1. **Identity matching / anchors**
   - AD + Okta matching must be correct (UPN / employeeID strategy). A mismatch can create duplicates or fail to link existing accounts.

2. **Manager attribute mapping**
   - AD may require `manager` as a DN string, not email. Incorrect mapping can break sync or validations.

3. **SCIM lag + eventual consistency**
   - If wait loops are not bounded or not implemented for all downstream systems, workflows will intermittently fail or race.

4. **Integration drift**
   - Ensure no integration module reintroduces “create user” logic for SCIM-managed apps.

5. **Bulk operations**
   - Any bulk offboarding tool must have explicit gates and dry-run mode.

---

## 7) What “Done” Looks Like (Acceptance Criteria)

SERVUS is considered production-ready when:

### Correctness
- Two-source confirmed events always lead to the right workflow selection.
- No duplicate side effects when re-running after crash/restart.

### Safety
- Offboarding requires explicit enablement for execution.
- Protected targets cannot be modified by automation.

### Observability
- A human can answer “what happened to user X?” using:
  - state checkpoints + structured logs + workflow traceability

### Operations
- Safe start/stop/restart documented.
- Clear “pause switch” / “kill switch” exists.
- Dry-run rehearsal scripts work for representative fixtures.

---

## 8) Next 3 Objectives (Focus)

1. **Formalize persistent idempotency keys + state transitions**
   - Ensure every event and workflow run has a stable ID and a recoverable step pointer.

2. **Harden wait-loop behavior**
   - Confirm Google + Slack + AD checks are bounded and emit actionable errors.

3. **Offboarding promotion workflow**
   - Define the mechanism to move from “pending offboard” to “execute offboard” with explicit approvals and audit stamp.

---

## 9) Where to Look First (Fast navigation)

- Architecture overview: `README.md`
- Best practices / SOP: `docs/Onboarding.md`
- Verification checklist: `docs/SERVUS_INSPECTION_PLAN.md`
- Workflows: `servus/workflows/*.yaml`
- Scheduler: `scripts/scheduler.py`
- Notes / continuity: `rolling_notes_for_servus.md`