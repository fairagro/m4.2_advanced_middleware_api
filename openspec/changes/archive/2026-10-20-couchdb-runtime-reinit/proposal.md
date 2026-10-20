# Proposal

## Why

If CouchDB is wiped or recreated while API (or Celery) processes keep running, the middleware keeps a stale “connected”
handle and never re-runs startup initialization. Writes then fail with unhandled `NotFoundError` (HTTP 500) until a pod
restart. Operators need runtime recovery without `kubectl rollout restart`.

## What Changes

- Add a single-flight `ensure_initialized()` path that re-runs the same work as startup (`connect` + system DBs + app DB
  - indices) when the application database is missing or the store is uninitialized.
- Invalidate / reconnect when the process still holds a client but the app DB no longer exists (today `connect()`
  early-returns if `_client is not None`).
- On the write path: detect app-DB-missing `NotFoundError`, trigger guarded re-init, retry the operation once; while
  re-init is in progress or permanently failing, surface **503** (actionable) instead of a generic 500.
- Strengthen readiness / CouchDB health: verify the **application database** exists (not only that the CouchDB server
  answers); fail readiness while the DB is missing or re-init has not succeeded; optionally trigger the same
  `ensure_initialized()` from the readiness path.
- Share the same recovery path for API and Celery long-lived store instances.
- OpenSpec delta for `document-store` (init + runtime recovery + readiness semantics).

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `document-store`: Runtime re-initialization when CouchDB app/system DBs disappear after process start; readiness must
  reflect application DB presence; recoverable missing-DB failures MUST NOT surface as unhandled 500 when re-init can
  run.

## Impact

- `CouchDBClient` / `CouchDB` document store (`connect`, `setup`, health); possibly `BusinessLogic.startup` /
  `health_check` and `ApiHealthService` readiness CouchDB check.
- HTTP: harvest/ARC writes may return 503 during re-init instead of 500.
- Celery workers that hold a document store across tasks.
- Channel: `build/issue-341-couchdb-runtime-reinit`. Related ops context: #337/#338 (DataHub wipe — out of scope).
