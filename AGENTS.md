# AGENTS.md (SERVUS)

This repo is **SERVUS**: a 24/7/365 new-hire provisioning + offboarding automation system.  
It listens for **paired triggers from two trusted sources**, cross-confirms them, then executes deterministic workflows with strong safety defaults.

## Prime Directive
**Do not make SERVUS “clever”. Make it correct, idempotent, and auditable.**  
When in doubt, prefer conservative behavior (log, stage, require confirmation) over irreversible actions.

---

## Non-Negotiables (Constitution)
1. **Two-source confirmation before action**
   - Never execute onboarding/offboarding actions unless the triggering event is confirmed by both configured sources.

2. **Idempotency**
   - Every workflow step must be safe to retry.
   - Re-running SERVUS after a crash must not duplicate side effects.

3. **Auditability**
   - Every external action must produce a structured log entry (who/what/where/when/result).
   - Every “why” decision should be captured (see *Decision Logging* below).

4. **Offboarding safety mode by default**
   - Offboarding must run in **log-only / dry-run / staged** mode unless explicitly enabled for execution.

5. **Protected targets are sacred**
   - If an object is in a protected OU/group/role list (or otherwise marked protected), abort the destructive step and raise a clear alert.

---

## Repo Map (high-level)
- `servus/` core package
  - `orchestrator.py` orchestration + state transitions
  - `workflow.py` + `workflows/*.yaml` workflow definitions (onboard/offboard)
  - `integrations/` external system adapters (Okta, Google, Slack, AD, Freshservice, Rippling, etc.)
  - `state.py` persistent state / dedupe (if present)
- `scripts/` operational entrypoints and diagnostics
  - `scheduler.py` main loop / polling driver
  - `dry_run_*` rehearsal tools
  - `emergency_offboard_*` emergency tooling
- `docs/` operational + planning docs
- `logs/` runtime logs (see note below)

---

## Logs Policy (IMPORTANT)
- **Do not open or analyze individual files in `logs/` unless explicitly asked.**
- You may acknowledge `logs/` exists and reference it as an output location.
- Prefer reasoning from code + docs over digging through logs.

---

## Change Discipline (to avoid rework)
SERVUS is a long-term project with high blast radius. Any meaningful change must also update at least one of:
- `rolling_notes_for_servus.md` (always)  
- `docs/Onboarding.md` and/or `docs/SERVUS_INSPECTION_PLAN.md` (when behavior changes)
- `docs/ADR/` (when a design/architecture decision changes or is introduced)

If code changes but docs/notes do not, assume the change is incomplete.

---

## Decision Logging (Continuity)
When making a decision that affects behavior, write an entry into `rolling_notes_for_servus.md` using this format:

- **DECISION:** what and why (1–3 lines)
- **CONTEXT:** what problem/risk prompted it
- **CONSEQUENCES:** what gets easier/harder
- **ROLLBACK:** how to undo safely
- **LINKS:** relevant files / workflow / integration modules

Keep entries short and searchable.

---

## Workflow Rules
- Workflows live in `servus/workflows/*.yaml`.
- Workflow steps must:
  - Validate inputs (required fields, formats, invariants)
  - Be safe to retry (idempotent)
  - Emit structured logs for every external call
  - Fail loudly with actionable error messages

### Offboarding
Offboarding steps must be:
- staged/log-only by default
- reversible where possible
- blocked on protected targets
- explicit about timing dependencies (e.g., directory replication delays)

### Onboarding
Onboarding steps must be:
- tolerant of provisioning lag (poll/wait for downstream accounts when needed)
- explicit about required prerequisites (manager, OU mapping, badge rules, etc.)

---

## Testing & Rehearsal
Before large changes:
- Prefer adding/using `scripts/dry_run_*` or fixture-driven simulations.
- If a behavior change touches an integration, add a small deterministic test or a dry-run scenario.

---

## Safety Defaults
- Minimize network access unless required.
- Never print secrets.
- Never persist secrets to repo files.
- Be careful with bulk operations; require explicit confirmation gates.

---

## How to Help Efficiently
When asked to implement or refactor:
1. Summarize the intended change in 3–6 bullets.
2. Identify risks + invariants that must hold.
3. Propose a minimal safe plan with rollback.
4. Make changes in small commits (or small logical steps).
5. Update `rolling_notes_for_servus.md` (and docs/ADR if needed).

---

## Red Flags (stop and ask)
Stop and ask for confirmation if:
- A change could remove access or delete/disable accounts
- A bulk operation could impact multiple users
- You’re unsure whether a target is protected
- There’s ambiguity in trigger confirmation logic
- You would need to inspect `logs/` to proceed

---

## Quick Commands (suggested)
- Run scheduler (dry-run if supported): `python -m servus` or `python scripts/scheduler.py`
- Rehearsal: `python scripts/dry_run_new_hires.py`
- Emergency offboard tooling: `python scripts/emergency_offboard_*.py`

(Adjust commands to match actual entrypoints when verifying.)