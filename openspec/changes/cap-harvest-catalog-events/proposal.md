# Proposal

## Why

Harvest documents append `catalog_events` on every catalog finalize and never drop old entries. Completing the same
harvest again is a supported recovery path and records another success even when Git does not push, so one document
grows for as long as that loop runs. ARC metadata already keeps a ring buffer (`max_event_log_size`). The cap belongs in
the harvest update path, so it stays when the document-store engine changes (#590).

## What Changes

- Persist at most a configurable number of newest `catalog_events` (default 100) when a harvest update appends one.
- Keep the event just appended. Do not change when success or failure events are recorded.
- Leave redundant success suppression and the uncapped harvest `errors` list out of this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `document-store`: A harvest update that appends a catalog event MUST retain only the configured newest entries.

## Impact

- `middleware/api/src/middleware/api/document_store/config.py` (`CouchDBConfig`) and
  `middleware/api/src/middleware/api/document_store/couchdb.py` (`update_harvest`).
- Unit tests for harvest catalog-event append.
- `openspec/specs/document-store/`.
- No HTTP contract change. `HarvestResponse` does not include `catalog_events`.
- No change to when `harvest-manager` records catalog success or failure.
