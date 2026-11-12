# Tasks

## 1. Model and counting API

- [x] 1.1 Add `warned_datasets` + `warnings` to `_DatasetCounts` / `RepositoryReport` snapshot
- [x] 1.2 Implement `RepositoryScope.record_warning(message, *, record_id=None, url=None)` (dataset-kind `HarvestIssue`;
      does not touch harvested/failed/skipped)
- [x] 1.3 Extend “callers do not own parallel counters” wording in code docs if present

## 2. JSON-LD + vocabulary

- [x] 2.1 Emit `fairagro:warnedDatasets` (always, including 0) and `fairagro:warnings` (when non-empty) using the same
      issue-node shape as failures
- [x] 2.2 Document the new terms in `ns/harvest-report/v2/` (README / context as applicable); keep vocabulary IRI on v2

## 3. Tests

- [x] 3.1 Unit tests: warning increments count + list; does not change failed/skipped; harvested-with-warning needs both
      calls
- [x] 3.2 JSON-LD tests: `warnedDatasets` 0 omits `warnings`; non-empty warnings array shape; failures still independent
- [x] 3.3 Run focused `uv run pytest middleware/shared/tests/unit/test_harvest_report.py` (and related) + ruff on
      touched files

## Workflow follow-up

- Draft PR after apply commits (`Fixes #630`); link harvester#637 and sql-to-arc#339 in the PR body
- Archive OpenSpec change on last `go` after merge-ready apply
