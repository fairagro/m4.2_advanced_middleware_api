# Proposal

## Why

Operators need per-RDI visibility into non-fatal harvest problems (e.g. title fallback when `schema:name` is missing).
Today those outcomes are only logged (and sometimes written as ARC comments); `HarvestReport` has no warnings channel,
so successful-but-degraded records are invisible in the JSON-LD report.

## What Changes

- Add a per-repository **warnings** channel on the shared harvest report, shaped like `failures`: count of warned
  datasets plus a list of `HarvestIssue`-compatible entries (kind/message, optional record id/URL).
- Add a counting API on the repository scope handle (`record_warning` / equivalent) that increments the warned-dataset
  count and appends a dataset-scoped issue **without** changing harvested / failed / skipped semantics.
- Serialize `fairagro:warnedDatasets` (including 0) and `fairagro:warnings` (when non-empty) on each EntryPoint in the
  JSON-LD v2 vocabulary (additive terms; no v3 bump).
- Document the new terms under `ns/harvest-report/v2/`.
- Unit tests for counting, isolation from failed/skipped, and JSON-LD shape.
- Consumer wire-up (harvester / sql-to-arc) is **out of scope** here — linked follow-ups:
  [harvester#637](https://github.com/fairagro/m4.2_middleware_harvester/issues/637),
  [sql-to-arc#339](https://github.com/fairagro/m4.2_sql_to_arc/issues/339).

## Capabilities

### New Capabilities

<!-- none — extend existing harvest-report -->

### Modified Capabilities

- `harvest-report`: Add record-warning requirements, snapshot/wire fields for warned datasets and warnings list, and
  JSON-LD EntryPoint mapping; clarify that warnings do not inflate failed/skipped.

## Impact

- Code: `middleware/shared/.../report/model.py`, `formats/jsonld.py`, unit tests under `middleware/shared/tests/`
- Vocabulary docs: `ns/harvest-report/v2/`
- Spec: `openspec/specs/harvest-report/`
- Downstream: harvester / sql-to-arc adopt after a shared release (separate issues)
