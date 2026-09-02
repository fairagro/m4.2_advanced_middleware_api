# Catalog finalize skip observability — Tasks

## 1. Finalize result type

- [ ] 1.1 Add a finalize outcome type (pushed, dataset_count, skipped
      `(arc_id, reason)` pairs) next to the ArcStore port.
- [ ] 1.2 Change `ArcStore.finalize` / `_finalize` to return that outcome;
      default no-op returns empty skips / `pushed=False` / `dataset_count=0`.
- [ ] 1.3 Update `ConsolidatedGitArcStore._finalize` to return the collect +
      publish outcome (including skips) instead of a bare bool.

## 2. Harvest catalog event message

- [ ] 2.1 In `ArcManager.finalize_catalog`, build `CATALOG_PUSH_SUCCESS`
      messages from the outcome; when skips > 0 include counts and a bounded
      list of skipped `arc_id`s (truncate with “+N more”).
- [ ] 2.2 Keep `CATALOG_PUSH_FAILED` / transient behaviour unchanged.

## 3. Tests

- [ ] 3.1 Unit: consolidated partial finalize outcome exposes skipped ids and
      dataset_count.
- [ ] 3.2 Unit: `finalize_catalog` SUCCESS event message contains skip summary
      when skips present; remains concise when zero skips.
- [ ] 3.3 Update existing finalize / business_logic tests that assumed `bool`.

## 4. Verify

- [ ] 4.1 Run focused `uv run pytest` for consolidated git + business_logic /
      harvest catalog event tests; ruff on touched paths.
