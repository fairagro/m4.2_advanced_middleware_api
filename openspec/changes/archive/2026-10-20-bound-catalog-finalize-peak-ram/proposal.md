# Proposal

## Why

Catalog finalize already streams CouchDB pages and keeps Dataset records only, but peak RAM still holds every included
Dataset and the full catalog bytes at the same time as the ephemeral Git clone and push. That peak is on the
consolidated Git path, which the PostgreSQL document-store cutover (#590) does not replace, so it should be bounded now.

## What Changes

- After the catalog file is fully serialized, drop the in-memory Dataset list before the ephemeral Git clone and push.
  Published bytes stay the same deterministic catalog as today.
- Keep the existing `catalog_list_page_size` knob (default 500). Document that operators can lower it under memory
  pressure. Do not change the default and do not add a new CouchDB pager.
- Leave the optional sort-key JSON micro-optimization out of this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `arc-store`: Consolidated finalize MUST release the in-memory Dataset collection before Git clone/push, without
  changing byte-stable catalog output or partial-push rules.

## Impact

- `middleware/api/src/middleware/api/arc_store/consolidated_git/store.py` (`_finalize` / `_publish_catalog_bytes`) and
  `catalog_serialize.py`.
- Unit tests for consolidated catalog finalize.
- `openspec/specs/arc-store/`.
- No HTTP contract change. No document-store engine change. Orthogonal to #590 and to shallow/sparse clone (#346).
