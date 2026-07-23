# ARC Ingestion Pipeline

**Scope:** The shared business logic that accepts a validated ARC payload, persists
it quickly in the document store, and schedules an async GitLab sync. It is
triggered by two HTTP endpoints (`arc-upload/` and `harvest-arc-upload/`) and
must not assume it runs inside an HTTP request. The GitLab sync itself is
specified in `arc-store/`.

## RoCrate wire contract

The `RoCratePayload` model (`middleware/shared/api_models/common/rocrate.py`) is
the single source of truth for structural ARC validation: `@context`, `@graph`, a
root data entity with `@id: "./"`, and a non-empty `identifier` (leading and
trailing whitespace trimmed). Text fields (`identifier`, `name`, `description`)
may be plain JSON strings, a single-element string array, or JSON-LD value
objects (`{"@value": "..."}`). Optional root fields `name` and `description` are
exposed as read-only properties but remain in `@graph` unchanged. See
`arc-manager/design.md` decision 4.

## Requirements

- [ ] Accept only a validated `RoCratePayload` (or raw dict validated to the
      RoCrate wire contract above). Validation is structural only — no arctrl
      parse on this path.
- [ ] Persist the validated ARC in the document store.
- [ ] Report `CREATED` when no prior record exists for this ARC.
- [ ] Report `UPDATED` when a prior record exists and the content has changed.
- [ ] Report `UPDATED` (idempotent) when a prior record exists and the content is
      identical to what is already stored — without writing to the store again.
- [ ] Schedule a background GitLab sync if and only if the ARC is new or its
      content has changed.
- [ ] During GitLab sync, delegate persistence to `arc-store/`; human-readable
      GitLab display metadata is derived there from the parsed arctrl ARC (see
      `arc-store/`).
- [ ] When a harvest context is provided, record harvest context on the ARC
      document via `DocumentStore.store_arc` (`last_harvest_id`, and
      `first_harvest_id` / `last_changed_harvest_id` when applicable). Per-harvest
      counters are derived at finalize via `get_harvest_statistics` (see
      `harvest-manager/`), not incremented on each ingest call.
- [ ] Return an internal result to the caller containing the ARC identifier, its
      status (`CREATED` or `UPDATED`), a timestamp, the originating `rdi`, and
      the caller's `client_id`. The HTTP layer (see `arc-upload/` and
      `harvest-arc-upload/`) decides which of these fields to expose in the
      HTTP response.

## Harvest-scoped identity rules

When a harvest context is provided, ARC identity within that harvest is
stable for the duration of the run:

- [ ] Re-submitting an ARC whose identifier was already recorded for this
      harvest **with identical content** (same content hash) reports
      `UPDATED` without writing a second document and without scheduling a
      second background sync — the call is idempotent and safe for transport
      retries.
- [ ] Re-submitting an ARC whose identifier was already recorded for this
      harvest **with different content** raises `DuplicateArcError` (mapped
      to `DuplicateArcInHarvestError` / HTTP `409` by harvest callers). The
      existing document must remain unchanged.
- [ ] Never create a second ARC document for the same `(identifier, rdi)`
      key; both success and conflict paths leave at most one object.

Standalone ingest (no harvest context) continues to allow content updates
across calls; see requirements above for `CREATED` / `UPDATED`.

## HTTP caller contract

Both `arc-upload/` and `harvest-arc-upload/` map outcomes as follows (unless an
endpoint-specific rule overrides):

| Condition | HTTP status |
| --------- | ----------- |
| Success (`CREATED` or `UPDATED`, including identical harvest re-submit) | `200 OK` |
| Invalid RO-Crate structure (`RoCratePayload` / `InvalidJsonSemanticError`) | `422 Unprocessable Entity` |
| Same identifier, different content in one harvest (`DuplicateArcInHarvestError`) | `409 Conflict` (harvest-arc-upload only) |
| Unexpected pipeline error (`BusinessLogicError`) | `500 Internal Server Error` |
| ARC stored but metadata fetch returns `None` | `500 Internal Server Error` |

`InvalidJsonSemanticError` is raised by `parse_rocrate` when Pydantic validation
fails; it denotes structural wire-format errors, not arctrl semantic failures.

## Edge Cases

Missing or invalid RO-Crate structure → `422` at the HTTP layer (`RoCratePayload`
validation). The worker re-validates queued JSON with `parse_rocrate`, then
parses with arctrl during Git sync; arctrl failures surface as failed sync
tasks / `GIT_PUSH_FAILED` events, not as HTTP `422` to the original caller.

RO-Crate JSON that passes API validation but cannot be parsed by arctrl →
accepted and stored in CouchDB; Git sync fails permanently in the worker.

Unchanged ARC re-submitted outside a harvest → no background sync scheduled;
`store_arc` still updates `last_seen` on the ARC document.

Unchanged ARC re-submitted inside the same harvest → idempotent `UPDATED`;
`last_seen` / `last_harvest_id` may be refreshed; no second sync; HTTP `200`.

Same identifier with different content inside the same harvest →
`DuplicateArcError` / HTTP `409`; document body and hash unchanged.

Two concurrent identical submissions for the same identifier in one harvest →
at most one document; both callers observe success (`CREATED` or `UPDATED`);
no `DuplicateArcError`.

Harvest counter increment fails → error propagates to the caller; the ARC is already
persisted at this point.

Unexpected error → wrapped and re-raised; caller maps this to `500`.
