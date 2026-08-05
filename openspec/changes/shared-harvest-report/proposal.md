# Shared Harvest Report — Proposal

## Why

Harvester and SQL-to-ARC both emit end-of-run reports as JSON-LD on stdout for
operators, but their shapes diverge (namespaces, nesting, failure detail). A
shared library in `middleware/shared` establishes one compatible harvest-report
contract—based on the newer harvester report—so client tools can depend on
`fairagro-middleware-shared` and produce the same operator-facing summary.

The first library cut modelled an end-of-run **snapshot** that callers fill by
maintaining their own counters. That is the wrong ownership boundary: both
[m4.2_middleware_harvester](https://github.com/fairagro/m4.2_middleware_harvester)
(`_ArcStreamState` increments) and
[m4.2_sql_to_arc](https://github.com/fairagro/m4.2_sql_to_arc)
(`ProcessingStats` increments) already treat statistics as an **accumulator
updated during the run**. The shared report MUST own that accumulation via
counting methods so client code only signals events.

Work remains scoped to this repository; consumer migrations happen separately.

## What Changes

- Provide a **mutable harvest-run report** that is initialised at harvest start
  and finished at harvest end, with per-repository scope handles (multiple MAY
  be open concurrently for parallel RDIs).
- Expose **counting methods** for harvest events (expected count, harvested,
  failed with detail, skipped, study/assay totals, harvest id). Callers MUST
  NOT maintain parallel counter state for fields the report already tracks.
  Callers SHOULD record harvested only after a definitive success (e.g. after
  ApiClient result), not optimistically before upload outcomes.
- Keep pluggable serialization (JSON-LD first) that returns a document string;
  wire shape stays the harvester baseline (`schema:Action` + `schema:result` of
  `EntryPoint`s, versioned `fairagro:` vocabulary under `ns/harvest-report/v2/`).
  Callers own stdout/logging of that string.
- Update Spec-to-Code mapping in `AGENTS.md` for the domain.
- **Non-goals:** changing `middleware/api` or `api_client` behavior; migrating
  consumer repos in this change; additional formats beyond JSON-LD; a shared
  stdout emit helper; machine parse/round-trip APIs; sql_to_arc-only PROV /
  instrument / actionStatus wire terms; custom apex-domain hosting; publishing
  all of `docs/` via Pages.

## Capabilities

### New Capabilities

- `harvest-report`: Mutable harvest-run accumulator with counting methods,
  format-neutral read model for serializers, and JSON-LD string rendering.

### Modified Capabilities

- (none — capability not yet archived to main specs)

## Impact

- **Code:** `middleware/shared/.../report/` becomes a start/count/finish API
  plus serializers (existing snapshot-only API is superseded in this change).
- **Vocab / Pages:** current serializer uses `ns/harvest-report/v2/` (v1 frozen
  with `failedRecords`); tag-gated publish of `ns/` only. The v2 wire
  (`fairagro:failures`) is intentionally not backward-compatible with v1
  `failedRecords`; no dual-emit / legacy serializer mode.
- **Package:** `fairagro-middleware-shared` public report API.
- **Specs:** delta under `openspec/changes/shared-harvest-report/`; main
  `openspec/specs/harvest-report/` after archive.
- **Out of scope repos:** consumer migrations only after the shared API
  stabilises.
