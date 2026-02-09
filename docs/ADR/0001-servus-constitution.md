# ADR 0001: SERVUS Constitution (Invariants & Safety Model)

- **Status:** Accepted
- **Date:** 2026-02-09
- **Owners:** IT Automation (SERVUS)
- **Applies To:** `servus/`, `servus/workflows/*.yaml`, `servus/integrations/*`, `scripts/scheduler.py`

## Context

SERVUS runs continuously (24/7/365) and performs identity lifecycle operations with real-world blast radius (access, accounts, physical entry). The system must remain correct under partial failure, retries, delayed downstream provisioning, and ambiguous triggers. SERVUS is operated primarily by a single engineer and must preserve continuity, reduce rework, and prevent “silent drift”.

SERVUS is designed to **augment** the IdP SCIM model by handling the “last mile” of validation and customization after Okta provisions downstream platforms. The system’s scheduler polls multiple sources to detect events and must confirm triggers before action.

## Decision

We define the following **non-negotiable invariants**. Any change that violates these requires a new ADR that explicitly supersedes this one.

### 1) SCIM-First, SERVUS as Customization & Validation Layer

- **Okta SCIM is the provisioner** for account creation, suspension/deactivation, and attribute replication where applicable.
- **SERVUS must not implement user creation flows** for downstream platforms that Okta SCIM provisions (e.g., Google, Slack, AD).  
- SERVUS may:
  - Validate existence and correctness (attributes, group membership, OU placement).
  - Apply post-provision customizations (OU moves, groups, channel membership, badge queueing).
  - Orchestrate sequencing and retries around SCIM delays.

### 2) Two-Source Trigger Confirmation Before Action

- SERVUS **must not execute onboarding/offboarding actions** unless the event has been cross-confirmed by two known-good sources (e.g., HRIS + ticketing).
- “Single-source only” may be supported for diagnostics, but must default to **dry-run** and be clearly labeled.

### 3) Offboarding Defaults to Safety Mode (Staged Execution)

- Offboarding is **high risk**. Default behavior is **log-only / staged**.
- SERVUS may generate a pending offboarding record (CSV/state) and notify, but must not execute destructive steps unless explicitly enabled.

### 4) Idempotency Is Mandatory

- Every step must be safe to retry.
- Re-running the scheduler after crash/restart must not:
  - Duplicate side effects (e.g., re-add channels repeatedly, re-move OUs endlessly).
  - Produce inconsistent end states.
- Each workflow should operate against a stable key (e.g., user email / worker ID) and should treat “already done” as success.

### 5) Explicit Handling of Provisioning Lag (Wait Loops)

- SERVUS must assume SCIM replication delays are normal.
- Any workflow that depends on the existence of a downstream account must:
  - Implement a bounded wait/poll loop (timeout with actionable error).
  - Avoid “sleep forever”.
  - Log progress and final failure cause.

### 6) Protected Targets Are Sacred (Hard Abort)

Certain identities/containers must never be modified by automation unless explicitly approved and documented (e.g., Super Admins, Service Accounts, Deo/Retention OUs, break-glass accounts).

- Steps that move, suspend, or remove access must:
  - Check a protected list.
  - **Abort** with a clear error if a target is protected.

### 7) Auditability and Forensics Are First-Class

- Every external action must produce a structured audit line containing:
  - workflow + step, target identity, system, action, result, timestamps, error (if any)
- “Why” decisions must be recorded in:
  - `rolling_notes_for_servus.md` (short entries), and
  - new ADRs when behavior/invariants change.

### 8) Logs Are Not a Data Dependency

- `logs/` is for human inspection and incident response only.
- SERVUS must not require log scraping for correctness.
- Tooling/agents should not open or parse individual log files unless explicitly requested.

### 9) Secrets Never Enter the Repo

- Secrets must be sourced from environment/config at runtime.
- No token dumps, no “temporary secrets” committed, no printing secrets to stdout.

## Consequences

### Positive
- Prevents accidental divergence from the SCIM-first model.
- Makes retries safe and predictable.
- Minimizes the probability of irreversible automation mistakes.
- Improves continuity for a solo engineer by forcing decisions to be recorded.

### Negative / Tradeoffs
- Some operations require “waiting for SCIM”, which adds latency.
- Strict safety defaults for offboarding add a manual confirmation step to go live.
- Extra checks (protected targets, idempotency) add implementation overhead.

## Guardrails (Required Practices)

1. **Docs move with code:** Any behavior change must update one of:
   - `docs/Onboarding.md`, `docs/SERVUS_INSPECTION_PLAN.md`, or an ADR
   - plus an entry in `rolling_notes_for_servus.md`
2. **No destructive defaults:** Offboarding execution must be opt-in and obvious.
3. **Prefer small steps:** Changes should be incremental and reversible.

## Alternatives Considered

1. **SERVUS provisions users directly**
   - Rejected: duplicates SCIM, increases drift risk, and creates split-brain authority.
2. **Single-source triggers**
   - Rejected: too risky; false positives cause real damage.
3. **No wait loops**
   - Rejected: SCIM lag is reality; failing fast would cause constant noise and rework.

## References

- `README.md` (architecture overview)
- `scripts/scheduler.py` (listener/poller)
- `servus/workflows/onboard_us.yaml`, `servus/workflows/offboard_us.yaml`
- `docs/Onboarding.md`, `docs/SERVUS_INSPECTION_PLAN.md`
- `rolling_notes_for_servus.md`