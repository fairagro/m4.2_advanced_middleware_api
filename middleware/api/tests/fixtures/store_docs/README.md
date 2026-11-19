# Store document golden fixtures (#652)

**Purpose:** Ensure tip Pydantic models can still **read** document generations we still support. This is an
**internal** persistence contract — not a public API SemVer / Conventional Commit `!:` gate (see #570 / #651).

## Allowlist (MVP)

| Model             | Directory  |
| ----------------- | ---------- |
| `HarvestDocument` | `harvest/` |
| `ArcDocument`     | `arc/`     |

Every `*.json` file directly under those directories is **supported** and must `model_validate` on tip. Do not put
unsupported/retired shapes there.

## When to add or keep a fixture

- On-disk / JSONB shape changes so older bytes must remain readable **and** that shape is not already covered → add a
  fixture **or** add backfill/default/`extra` so existing fixtures stay green.
- Additive optional fields with defaults usually need **no** new fixture.
- Prefer store-agnostic envelopes (domain models). Minimal `arc_content` stubs are enough; do not treat full RO-Crate
  graphs as the compatibility surface here.

## When to retire a fixture

- Generation no longer supported (migration done + support window over), **or**
- [#590](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/590) Postgres cutover **without** CouchDB data
  migration — pre-cutover CouchDB-era archaeology fixtures may be deleted then.

Move out of these directories (or delete). Retired files must not be loaded by the suite.

## Non-goals

- Tip-vs-`main` JSON Schema / oasdiff-style CI job
- Coupling failures to `type!:` / `BREAKING CHANGE:`
- Validating production database contents
- Automatic “current snapshot” drift tooling (optional later)

## Tests

`middleware/api/tests/unit/test_store_doc_golden_fixtures.py` loads every supported `*.json` and validates with the tip
model.
