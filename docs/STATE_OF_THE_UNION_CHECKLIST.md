
```md
# docs/STATE_OF_THE_UNION_CHECKLIST.md

# SERVUS: Weekly State of the Union Checklist

- **Cadence:** Weekly (or before major merges/releases)
- **Goal:** Prevent drift, preserve safety posture, and keep SERVUS predictable.
- **Time budget:** 15–30 minutes

> Rule: If you can’t answer a checkbox quickly, that’s the signal to capture a note, add an ADR, or write a small test.

---

## A) Constitution Compliance (Invariants)

- [ ] **SCIM-first authority is intact**  
  No new “create user” logic added for SCIM-managed platforms (Google/Slack/AD as configured).

- [ ] **Two-source confirmation is enforced**  
  No production path executes onboarding/offboarding from a single unconfirmed source.

- [ ] **Offboarding defaults to staged/log-only**  
  Execution requires explicit enablement (flag/config/approval gate).

- [ ] **Protected targets are enforced**  
  Destructive steps abort on protected OUs/accounts/groups (no bypasses added silently).

- [ ] **Idempotency still holds**  
  Rerunning workflows does not duplicate side effects (channels/groups/OU moves) and “already done” resolves as success.

- [ ] **Wait loops are bounded**  
  Any “wait for SCIM” behavior has a timeout and emits actionable error messages.

---

## B) Workflow Health (onboard/offboard)

- [ ] **Workflow files are in sync with code**  
  `servus/workflows/onboard_us.yaml` and `offboard_us.yaml` reference valid step names and inputs.

- [ ] **Onboarding happy path rehearsal passes (dry-run)**  
  Run representative dry-run script(s) (example: `scripts/dry_run_new_hires.py`) and confirm no regressions.

- [ ] **Offboarding rehearsal passes (staged mode)**  
  Confirm the staged/offboarding preview produces expected “would do” actions without executing.

- [ ] **No new bulk action paths lack explicit gates**  
  Any bulk tooling requires dry-run, confirmation, and clear scoping.

---

## C) Integrations Drift Check

For each integration in `servus/integrations/` that changed this week:

- [ ] **Inputs validated**
  Required fields are checked with clear errors (missing email, worker_id, manager, etc.).

- [ ] **Retries are safe**
  External calls are safe to retry; rate limits and transient errors handled.

- [ ] **Structured audit logs exist**
  Each external call logs workflow/step/system/action/target/result.

- [ ] **No secret leakage**
  No credentials printed; no tokens placed in repo files.

---

## D) State, Recovery, and Continuity

- [ ] **Restart behavior is safe**
  Stopping and restarting the scheduler does not duplicate side effects or lose track of pending work.

- [ ] **Idempotency keys are stable**
  Confirm event identification/dedupe logic still anchors to stable fields (email/worker_id/effective_date).

- [ ] **“What happened to user X?” is answerable**
  Using state checkpoints + structured logs + workflow trace, you can reconstruct actions for a user.

- [ ] **Rolling notes updated**
  `rolling_notes_for_servus.md` includes:
  - CHANGE entries for code changes
  - DECISION entries for behavioral changes
  - NEXT for the next milestone step

---

## E) Docs & ADR Hygiene

- [ ] **STATE_OF_THE_UNION is current**
  If architecture or posture changed, update `docs/STATE_OF_THE_UNION.md`.

- [ ] **ADR created for major decisions**
  If any invariant/authority/safety boundary changed, add a new ADR.

- [ ] **Inspection plan reflects reality**
  If operational verification changed, update `docs/SERVUS_INSPECTION_PLAN.md`.

---

## F) Quick “Red Flag” Scan (stop-the-line)

If any of these are true, stop and address before shipping:

- [ ] A change enables destructive offboarding by default
- [ ] A path executes from a single unconfirmed trigger
- [ ] A protected target can be modified
- [ ] A workflow step is not idempotent
- [ ] An integration prints or stores secrets
- [ ] Wait loops can hang indefinitely

---

## Completion Notes

- **Date:** __________
- **Reviewer:** __________
- **Summary (3 bullets):**
  1. __________________________
  2. __________________________
  3. __________________________

- **Top risk to address next:** __________________________
- **Next action:** __________________________