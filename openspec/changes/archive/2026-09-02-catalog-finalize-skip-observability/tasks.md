# Catalog finalize skip observability — Tasks

## 1. Finalize result type

- [x] 1.1 Add a finalize outcome type (pushed, dataset_count, skipped
      `(arc_id, reason)` pairs) next to the ArcStore port.
- [x] 1.2 Change `ArcStore.finalize` / `_finalize` to return that outcome;
      default no-op returns empty skips / `pushed=False` / `dataset_count=0`.
- [x] 1.3 Update `ConsolidatedGitArcStore._finalize` to return the collect +
      publish outcome (including skips) instead of a bare bool.

## 2. Harvest catalog event message

- [x] 2.1 In `ArcManager.finalize_catalog`, build `CATALOG_PUSH_SUCCESS`
      messages from the outcome; when skips > 0 include counts and a bounded
      list of skipped `arc_id`s (truncate with “+N more”).
- [x] 2.2 Keep `CATALOG_PUSH_FAILED` / transient behaviour unchanged.

## 3. Tests

- [x] 3.1 Unit: consolidated partial finalize outcome exposes skipped ids and
      dataset_count.
- [x] 3.2 Unit: `finalize_catalog` SUCCESS event message contains skip summary
      when skips present; remains concise when zero skips.
- [x] 3.3 Update existing finalize / business_logic tests that assumed `bool`.

## 4. Verify

- [x] 4.1 Run focused `uv run pytest` for consolidated git + business_logic /
      harvest catalog event tests; ruff on touched paths.
