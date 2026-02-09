# docs/ADR/0000-index.md

# SERVUS ADR Index

This file is the table of contents for SERVUS Architecture Decision Records (ADRs).

**How to use**
- Read **0001** first. It defines SERVUS’s invariants and safety posture.
- If an ADR is **Superseded**, follow the link to the newer ADR and treat that as the current truth.
- Keep this index updated whenever a new ADR is added or an ADR changes status.

---

## Active (Accepted)

- **[ADR 0001: SERVUS Constitution (Invariants & Safety Model)](0001-servus-constitution.md)**  
  Status: Accepted  
  Defines: authority boundaries, two-source confirmation, offboarding safety defaults, idempotency, protected targets, auditability.

---

## Proposed

> None yet.

---

## Deprecated

> None yet.

---

## Superseded

> None yet.

---

## Conventions

- File naming: `NNNN-short-title.md`
- Status values: Proposed | Accepted | Deprecated | Superseded
- When superseding an ADR:
  1. Create the new ADR with status **Accepted**
  2. Mark the old ADR as **Superseded**
  3. Add a line to the old ADR: “Superseded by ADR NNNN: …”
  4. Update this index under **Superseded**

---

## Maintenance Checklist (quick)

When adding a new ADR:
- [ ] Create `docs/ADR/NNNN-title.md`
- [ ] Set Status + Date
- [ ] Add it to this index in the correct section
- [ ] If replacing an ADR, mark the old one as Superseded and link both ways