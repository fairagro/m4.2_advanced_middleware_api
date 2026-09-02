# Harvest statistics pagination — Tasks

## 1. Paginate statistics query

- [x] 1.1 Update `CouchDB.get_harvest_statistics` to loop `find_projected` pages until a short page (use
      `CouchDBConfig.default_query_limit` / `self._config.default_query_limit` as page size).
- [x] 1.2 Aggregate `arcs_submitted`, `arcs_new`, `arcs_updated`, and `arcs_unchanged` across all pages with
      unchanged classification rules.

## 2. Tests

- [x] 2.1 Extend `test_get_harvest_statistics` (or add sibling test) simulating > `default_query_limit` projected
      rows across multiple pages; assert full counts.
- [x] 2.2 Add harvest-manager or integration-level test that finalize persists correct totals for a large
      harvest mock (optional if couchdb unit test covers store contract).

## 3. Verify

- [x] 3.1 Run `uv run pytest middleware/api/tests/unit/test_couchdb_store.py -q` and related harvest-manager
      tests.
- [x] 3.2 Close [#345](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/345) when merged.
