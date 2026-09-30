# Proposal

## Why

`arc_id` is `SHA-256(identifier.strip() + ":" + rdi.strip())`. True cryptographic collisions are negligible, but
identity integrity still fails when a document already exists at `arc_{arc_id}` whose stored `(identifier, rdi)` do not
match the incoming pair under those strip rules (bugs, encoding surprises, or a real collision). Today `store_arc`
updates that document by key alone and can silently overwrite another ARC's body. Issue
[#101](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/101) asks to detect such collisions and refuse
the dangerous overwrite.

## What Changes

- On update of an existing `arc_{arc_id}` document, verify that the stored identifier and `rdi` match the incoming
  values under the same `.strip()` rules used by `calculate_arc_id`.
- On mismatch (including a true hash collision, which presents the same way): do **not** overwrite; raise a distinct
  conflict error and map it to HTTP `409 Conflict` for both standalone and harvest-scoped upload.
- Matching identity continues the existing content-hash / harvest-local duplicate paths unchanged.
- **Out of scope:** Unicode NFC (or stronger) canonicalize-before-hash — deferred to
  [#537](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/537) (breaking `arc_id` rename). No
  `content_hash` algorithm changes. GitLab / git metadata checks are not the primary gate.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `document-store`: Require identity verification before updating an existing ARC document; refuse mismatch without
  writing the body.
- `arc-manager`: Surface the identity-mismatch failure through the ingestion pipeline and extend the shared HTTP outcome
  mapping so callers get `409`.
- `arc-upload`: Standalone `POST /v3/arcs` returns `409 Conflict` on identity mismatch (no document overwrite).
- `harvest-arc-upload`: Harvest `POST /v3/harvests/{harvest_id}/arcs` returns `409 Conflict` on identity mismatch (same
  as existing harvest duplicate-content conflicts; distinct error type/message).

## Impact

- **Code:** `DocumentStore.store_arc` / CouchDB path (`middleware/api/.../document_store/couchdb.py`), identity
  extraction from stored `arc_content` + top-level `rdi`, new exception type (or reuse of a conflict subclass),
  `ArcManager` catch/map, HTTP handlers in `api/v3/arcs.py` and `api/v3/harvests.py`.
- **APIs:** New `409` failure mode on standalone upload; harvest already uses `409` for content conflicts — extend for
  identity mismatch.
- **Issues:** Implements MVP Option 1 for [#101](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/101);
  NFC follow-up remains [#537](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/537).
- **No migration:** Strip-only compare against already-stored fields; no `arc_id` formula change.
