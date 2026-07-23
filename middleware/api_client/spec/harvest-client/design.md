# Harvest Client — Design

## Module Overview

`ApiClient` (`api_client.py`) orchestrates the harvest lifecycle.
`HarvestResult`, `HarvestStatistics`, `HarvestError`, and `HarvestErrorType`
(`models.py`) are the stable public types exposed to harvesters.

```text
harvester
    └─→ ApiClient.harvest_arcs(rdi, arcs)
            ├─→ create_harvest          → HarvestResult (RUNNING)
            ├─→ _submit_arcs_parallel
            │       ├─→ duplicate check (client-side)  → HarvestError(DUPLICATE)
            │       └─→ POST v3/harvests/{id}/arcs      → HarvestError(SUBMISSION_FAILED) on error
            └─→ complete_harvest        → HarvestResult (COMPLETED)
                    └─→ inject client_errors via model_copy  → HarvestResult.errors
```

## Key Decisions

1. **`HarvestStatistics` is a typed Pydantic model, not `dict`**
   — The server serializes its internal `HarvestStatistics` via `model_dump()`
   before sending it over the wire. The field names and types are stable and
   known. A typed model gives consumers validated, IDE-navigable fields rather
   than requiring dict key lookups with no type safety.

2. **`HarvestError` is a client-facing type in `models.py`, independent of any server model**
   — Per-item errors are currently generated client-side. When the server
   persists them natively (issue #240), `_parse_harvest_response` will
   populate `HarvestResult.errors` from the server response automatically —
   the type and consumer interface remain unchanged.

3. **`arc_id: str | None` in `HarvestError`**
   — The `DUPLICATE` and `SUBMISSION_FAILED` categories always have a
   known ARC identifier (when one is extractable from the RO-Crate). Future
   error categories — such as harvest-level timeouts or config failures —
   may not be associated with any specific ARC. `None` is the semantically
   correct representation; an empty string would be an invisible sentinel
   value that callers would need to treat specially.

4. **Client-side error collection as compatibility shim until issue #240**
   — `harvest_arcs()` collects errors from `_submit_arcs_parallel()` and
   merges them into the server response via `model_copy(update=...)`.
   This shim is removed once the server persists and returns per-item errors
   natively. The `model_copy` merge is additive: if the server already
   returns errors in its response (post-#240), client-side errors are
   appended rather than overwriting.

5. **Duplicate detection is performed client-side before the HTTP request**
   — Within one harvest batch, two different ARC payloads that share an
   identifier are a harvester bug. Detecting them client-side yields an
   explicit `DUPLICATE` error and avoids the round-trip. The server still
   enforces harvest-local identity: identical re-submits (e.g. transport
   retries) return `200`; conflicting content for the same identifier returns
   `409` (see `harvest-arc-upload/`). Client-side detection therefore covers
   *intra-batch* duplicates; server idempotency covers *retry* duplicates.

6. **Item-level failures are non-fatal; harvest-level failures are fatal**
   — A submission failure for one ARC (e.g. server 422 on bad content) must
   not abort the entire harvest because the remaining ARCs may be valid. A
   catastrophic failure (e.g. 401 Unauthorized, harvest already closed) means
   no further submissions will succeed, so the harvest is aborted, marked
   `FAILED`, and the exception propagates to the caller.

7. **POST ARC endpoints are retryable only after server harvest idempotency**
   — Once `POST …/arcs` treats identical harvest re-submits as `200`, the
   client may retry `ConnectError` (and optionally timeouts) on those POSTs
   without risking a second object or a spurious catastrophic `409`. Conflicting
   `409` (same identifier, different content) remains a real conflict and must
   not be retried as success.
