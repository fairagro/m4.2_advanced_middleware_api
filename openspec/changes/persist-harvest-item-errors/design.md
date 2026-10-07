# Design

## Context

See proposal.md — Why. Client already defines `HarvestError` / `HarvestErrorType` and `HarvestResult.errors`. Server
`HarvestStatistics.errors` remains an **int** count (separate from the new top-level list). Wire `HarvestResponse` has
no error list yet. Harvest-scoped conflicts already map to HTTP `409`.

## Goals / Non-Goals

**Goals:**

- Durable per-item errors on the harvest document and GET/list responses.
- Record server-observed harvest upload failures that already return `409`.
- Backward-compatible defaults for old documents and old clients (ignore unknown fields / default `[]`).

**Non-Goals:**

- Any change that breaks retry-safety (same identifier + identical content → `200` / `UPDATED`). Rejecting that path
  with `409` is forbidden by `harvest-arc-upload` and is not a future option (#565 → will-not-do).
- Removing the client shim (#566).
- Error pagination (#567).
- Recording every client-only skip that never reaches the API (still shim territory).

## Decisions

### D1: Top-level `errors` list vs reuse `statistics.errors`

Keep `statistics.errors` as the integer counter. Add `HarvestDocument.errors: list[HarvestError]` and the same on
`HarvestResponse`. When appending an item error, also increment `statistics.errors` (or set it to `len(errors)` on
read/finalize) so existing count consumers stay coherent.

**Reason:** Avoid overloading the int field; matches the client model shape (`HarvestResult.errors` list +
`statistics.errors` int).

### D2: Shared wire `HarvestError` in `api_models/v3`

Define `HarvestErrorType` and `HarvestError` next to `HarvestResponse` in shared models; document store may re-export or
embed the same schema. Client keeps its independent models but maps 1:1 from wire JSON.

**Reason:** One HTTP contract; client already documents independence from server modules.

### D3: Append on `409` harvest upload paths only (MVP)

In the harvest ARC upload handler (or `ArcManager` before re-raise), after classifying `DuplicateArcInHarvestError` /
`ArcIdentityMismatchError`, append:

- content conflict → `error_type=duplicate` (identifier + message)
- identity mismatch → `error_type=submission_failed` (or a dedicated type only if already on the wire enum — MVP uses
  `submission_failed` to avoid a new enum value unless specs require `duplicate` for both)

Do not append on successful `200` retries. Never flip identical-content retries to `409` in order to record a
`duplicate` error — that would violate retry-safety.

**Reason:** Smallest server-visible failure set; preserves the retry-safe HTTP contract.

### D4: Concurrent appends

Use CouchDB document update with revision retry (existing harvest update patterns) or an atomic append helper so
parallel harvest workers do not drop errors.

**Reason:** Harvest ARC POSTs are concurrent.

### D5: Client merge stays

`harvest_arcs()` continues to collect client-side errors and merges with any server `errors` from the completed harvest
GET/complete response (`model_copy` / list concat with stable de-dup if cheap).

**Reason:** Locked non-breaking MVP; removal is #566.

## Risks / Trade-offs

- [In-batch same-content duplicates still only on client] → Accepted until #566; server never saw the skipped POST.
- [Large error lists on one GET] → Deferred to #567; MVP returns the full array.
- [statistics.errors vs len(list) drift] → Prefer updating both in the same append path.

## Migration Plan

Deploy API first (additive JSON). Old clients ignore `errors`. Old harvest docs load with `errors=[]`. Rollback is
revert; leftover `errors` fields are ignored via `extra="ignore"` where configured.
