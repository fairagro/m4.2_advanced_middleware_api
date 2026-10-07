# Proposal

## Why

Per-item harvest errors (content conflicts, identity mismatches) are only retained in the API client shim today.
`GET /v3/harvests/{id}` cannot show which ARCs failed, so dashboards and post-hoc diagnosis have no server source of
truth. [#240](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/240) asks for CouchDB persistence; this
change lands the **non-breaking** slice only.

## What Changes

- Persist a typed `errors` list on the harvest document (default `[]` for existing CouchDB rows).
- Expose the same list on `HarvestResponse` (additive wire field).
- Append an error when harvest-scoped upload fails with content conflict (`409` / `DuplicateArcInHarvestError`) or
  identity mismatch (`409` / `ArcIdentityMismatchError`), without changing those HTTP status codes.
- Keep identical-content re-submit as `200` (no `DUPLICATE` row for successful retries). Retry-safety is a hard contract
  (`harvest-arc-upload`: **Remain retry-safe for identical harvest content**); this change MUST NOT weaken it.
- Map server `errors` into `HarvestResult.errors` in the API client; **keep** the client-side shim merge until
  follow-ups land.
- OpenSpec updates for `harvest-manager`, `harvest-arc-upload`, and `harvest-client`.

Invariant (not negotiable):

- Harvest ARC upload stays retry-safe: same identifier + identical content → HTTP `200` / `UPDATED`, never `409` only
  because the identifier was seen before. Rejecting that path would break lost-response retries and is out of scope
  forever for this API (rejected Option-C idea;
  [#565](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/565) should be closed as will-not-do).

Deferred (linked issues):

- Remove client duplicate-skip / error shim →
  [#566](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/566)
- Paginate `errors` on GET → [#567](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/567)

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `harvest-manager`: Harvest documents and GET/list responses MUST carry a typed per-item `errors` list (default empty).
- `harvest-arc-upload`: On harvest-scoped content conflict or identity mismatch, the server MUST append a corresponding
  harvest error before returning the existing `409` mapping.
- `harvest-client`: MUST surface server-persisted errors on harvest query/complete results while retaining the temporary
  client-side collection merge for errors the server does not yet see (e.g. skipped in-batch duplicates).

## Impact

- `middleware/api/.../harvest_document.py`, document store append API, `arc_manager` / harvest upload error paths,
  `api/v3/harvests.py` mapping, shared `api_models/v3`, `api_client` harvest mapping.
- No change to successful upload status codes or retry-`200` semantics; retry-safety remains mandatory.
- Channel: `build/issue-240-server-harvest-errors`.
