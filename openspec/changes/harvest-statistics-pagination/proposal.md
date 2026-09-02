# Harvest statistics pagination — Proposal

## Why

`CouchDB.get_harvest_statistics` loads ARC documents through `find_projected` with a single call capped at
`default_query_limit` (default **100**) (see [#345](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/345)).
Harvests with more than 100 ARCs last seen get **under-counted** terminal statistics (`arcs_new`, `arcs_updated`,
`arcs_unchanged`, `arcs_submitted`).

That is incorrect on its own and becomes operationally dangerous with the consolidated Git catalog: completion
flows that rely on accurate change counts can mis-classify a harvest as having no new/updated ARCs and skip or
delay catalog finalize, leaving `{rdi}.json` stale on the shared remote.

## What Changes

- Paginate `CouchDB.get_harvest_statistics` until all matching ARC metadata rows are scanned (page loop on
  `find_projected`; bookmark-based paging when the client already supports it on the branch).
- Aggregate statistics across pages; preserve existing classification rules (`first_harvest_id`,
  `last_changed_harvest_id`).
- Add unit tests with more than `default_query_limit` ARC documents for one harvest id.
- Document-store and harvest-manager specs gain explicit requirements for complete statistics beyond the default
  query cap.

Non-goals: changing how ARCs are classified; altering HTTP harvest API shapes; replacing Mango with a different
index strategy in this change.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `document-store`: `get_harvest_statistics` MUST scan all matching ARC docs, not just the first query page.
- `harvest-manager`: terminal statistics MUST reflect every ARC last seen in the harvest, including when count
  exceeds `default_query_limit`.

## Impact

- Code: `middleware/api/src/middleware/api/document_store/couchdb.py`,
  `middleware/api/src/middleware/api/document_store/couchdb_client.py` (if paging helper is shared).
- Tests: `middleware/api/tests/unit/test_couchdb_store.py` (and harvest-manager tests if needed).
- Fixes [#345](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/345).
- Branch: `fix/harvest-statistics-pagination` (off current `main`).
