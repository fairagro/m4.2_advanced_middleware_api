# Proposal

## Why

Harvest completion (`POST /v3/harvests/{id}/complete`) is not retried by the API client today. After ARC uploads
succeed, a single `httpx.ConnectError` (or other transient failure) before an HTTP response leaves the harvest
non-completed and the RDI reported failed — even when the server may already have applied `COMPLETED`. Deferred from
#305; observed in production-style harvest runs (issue #547).

Server-side re-complete of an already-`COMPLETED` harvest is already an idempotent no-op that re-enqueues catalog
finalize. Catalog finalize is byte-stable: a second run with the same ARC set skips commit/push, so double finalize is
safe for catalog Git content.

## What Changes

- **ApiClient / harvest-client:** Treat harvest completion POSTs as retryable for the same transport/transient policy as
  idempotent ARC POSTs (`ConnectError` / `RequestError` except timeouts; HTTP `502`/`503`/`504`).
- **Client-Defense GET:** After a failed completion attempt (exhausted retries or non-retryable failure path as
  designed), `GET` the harvest; if status is already `COMPLETED`, treat completion as success; if still `RUNNING`, allow
  retry of complete where applicable.
- **Specs:** Update `harvest-client` to require completion retries and the GET defense; clarify in `harvest-manager` (or
  cross-reference) that re-complete + re-finalize remains the recovery path and is safe when the ARC set is unchanged.
- **Not BREAKING** for well-behaved clients; clients that previously treated any complete failure as fatal will now
  recover more often.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `harvest-client`: Allow (require) retry of harvest completion POSTs; add post-failure GET defense when status is
  already `COMPLETED`.
- `harvest-manager`: Clarify (if needed) that COMPLETED replay re-enqueues finalize and that byte-stable catalog
  finalize makes an unchanged second run a Git no-op — no behavioural flip from Option B.

## Impact

- **Code:** `middleware/api_client/.../api_client.py` (`_is_idempotent_post_path` / complete path + GET defense); unit
  tests for client retry and lost-response-style success via GET/`COMPLETED`.
- **Server:** No required behaviour change for Option A (already re-complete + re-finalize); tests may only assert
  existing contract if gaps remain.
- **Out of scope:** Idempotency-Key on complete; cancel/fail semantics; fixing ingress ConnectErrors; changing finalize
  when ARC set actually changed.
