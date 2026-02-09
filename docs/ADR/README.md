# docs/ADR/README.md

# Architecture Decision Records (ADRs)

This folder contains **Architecture Decision Records** for SERVUS.

ADRs exist to prevent:
- repeating the same design debates,
- forgetting why something was done,
- accidental drift when refactoring,
- “solo engineer amnesia” during long projects.

If a change has **blast radius** (safety, authority, data model, workflows, idempotency, or integrations), it deserves an ADR.

---

## When to write an ADR

Write an ADR when you are:
- changing **authority boundaries** (e.g., SCIM-first vs. direct provisioning)
- changing **trigger rules** (two-source confirmation, event anchoring)
- changing **offboarding safety posture**
- changing **workflow architecture** (YAML, step engine, orchestration model)
- changing **state/idempotency strategy**
- changing **security posture** (secrets, network access, sandbox, protected targets)
- introducing or deprecating a major integration or execution path

If the change could cause:
- access removal,
- account creation/deletion,
- permission escalation,
- bulk impact,
- compliance implications,

…write an ADR.

---

## ADR naming & numbering

- Files live in: `docs/ADR/`
- Naming format: `NNNN-short-title.md`
  - Example: `0001-servus-constitution.md`
- Numbering:
  - Start at `0001`
  - Increment by 1 for each new ADR
  - Do not reuse numbers

---

## ADR template (copy/paste)

Create a new file `docs/ADR/NNNN-title.md` and use:

```md
# ADR NNNN: <Title>

- **Status:** Proposed | Accepted | Deprecated | Superseded
- **Date:** YYYY-MM-DD
- **Owners:** <team/person>
- **Applies To:** <paths/modules/workflows>

## Context
What problem are we solving? What constraints exist? What risks are in play?

## Decision
What are we doing? Be explicit. Define invariants and boundaries.

## Consequences
### Positive
What gets better / easier / safer?

### Negative / Tradeoffs
What gets worse / harder / slower?

## Alternatives Considered
List 2–3 real alternatives and why they were rejected.

## Rollback / Migration Plan
How do we undo this decision safely? If there’s a phased rollout, describe it.

## References
Links to files, docs, tickets, diagrams, examples.