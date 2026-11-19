# Design

## Context

See `proposal.md` / issue #652. Persist models already live in `middleware/api/.../document_store/` (`HarvestDocument`,
`ArcDocument`, …) with some forward-compat (`extra="ignore"`, backfills). Public surface gates (#570 / #651) are out of
scope. #590 will cut over to Postgres+JSONB **without** migrating CouchDB data.

## Goals / Non-Goals

**Goals:**

- CI-enforced read-compat for **known supported** on-disk/JSONB-like shapes via fixtures + `model_validate`
- Clear human/agent rules for add vs retire; store-agnostic fixtures where possible
- Thin MVP: two types, few fixtures, docs

**Non-Goals:**

- Tip-vs-`main` JSON Schema / oasdiff-style diff job
- Conventional Commit `!:` / SemVer coupling
- Validating production DB contents
- “Current snapshot drift” updater tool (optional later)
- Expanding allowlist to `TaskRecord` / idempotency / locks in MVP

## Decisions

1. **Mechanism = golden fixtures + pytest**, not a schema-diff gate. Failures mean tip cannot load a still-supported
   example. Additive optional fields usually need no new fixture.

2. **Allowlist MVP = `HarvestDocument` + `ArcDocument`.** ARC fixtures use a minimal `arc_content` stub sufficient for
   the model, not full RO-Crate graphs.

3. **Lifecycle**
   - Add/keep: when older bytes must remain readable and are not already covered (or add backfill so existing fixtures
     stay green).
   - Retire: delete/exclude when unsupported; document #590 as retire point for Couch-only archaeology.
   - Daily memory: not required — CI fails on break; README checklist for intentional shape-change PRs.

4. **Layout** `middleware/api/tests/fixtures/store_docs/` (name store-agnostic) + `README.md` +
   `test_store_doc_golden_fixtures.py` (or under `tests/unit/`). Stay in product tests; do not invent
   `tools/contract-gates` for this slice (#724 remains separate).

5. **Capturing fixtures** Prefer realistic reduced dumps from existing shapes / comments in models (e.g.
   pre-`client_id`, pre-`last_changed`). No live CouchDB required for the unit tests.

## Risks / Trade-offs

- **[Risk] Fixtures drift from real prod** → Mitigation: start from known historical gaps already documented in models;
  refresh when fixing prod read bugs.
- **[Risk] Over-collection of Couch-only edges before #590** → Mitigation: keep fixture count small; README points at
  #590 retire.
- **[Trade-off] No automated “you forgot a current fixture”** → Accepted for MVP; checklist only.

## Migration Plan

- Land fixtures + tests + docs on the issue branch; no runtime deploy change.
- After #590 cutover: retire Couch-era-only fixtures in that (or follow-up) PR.

## Open Questions

- None blocking MVP; exact fixture filenames left to apply.
