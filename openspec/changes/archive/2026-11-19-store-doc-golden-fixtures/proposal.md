# Proposal

## Why

Persisted harvest/ARC document shapes are an **internal** store contract. Unlike public Python (#570) or HTTP `/v3`
OpenAPI (#651) gates, shape evolution is healed with backfills, defaults, and migrations — not SemVer `!:`. What must
not regress is **tip code still loading document generations we still support**. CI cannot certify production DBs; it
can certify **known** older JSON shapes via golden fixtures + `model_validate` (#652 explore lock-in).

## What Changes

- Add allowlisted golden JSON fixtures for MVP types `HarvestDocument` and `ArcDocument` (store-agnostic envelopes)
- Add unit tests that tip models successfully `model_validate` every **supported** fixture
- Document fixture lifecycle (when to add/keep vs retire), explicit non-goals (no tip-vs-`main` schema-diff gate; no
  Conventional Commit coupling), and retire note for CouchDB-era fixtures at Postgres cutover (#590)
- Product-local only; no Devinfra fleet fragment

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `document-store`: Require golden-fixture read-compatibility checks for allowlisted persisted document models

## Impact

- Tests/fixtures under `middleware/api/tests/` (and a short README beside fixtures)
- Docs: product-local note (e.g. under `docs/` or fixture README); cross-link from surface-quality bar only if needed
- Issue: #652; related #570 / #651 (public, out of scope here); #590 (cutover retires Couch-era fixtures)
- No runtime API or CI job beyond existing pytest in code-quality
