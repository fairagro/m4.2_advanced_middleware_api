# Proposal

## Why

Catalog finalize can enqueue overlapping Celery tasks for the same RDI (concurrent harvest completes, re-complete
retries), causing Git non-fast-forward churn and `max_retries` burn. Separately, harvest-scoped ARC submit after
`COMPLETED`/`CANCELLED`/`FAILED` still succeeds, so ARCs can land after finalize was enqueued and leave the catalog
lagging until a later harvest. Scope is issue #348 items **A** and **C** only (not **B** re-read-after-clone; not
blocked on #590 PG cutover).

## What Changes

- **A:** Per-RDI **single-flight** for catalog finalize: overlapping finalize work for one RDI MUST NOT run concurrent
  heavy clone/rebuild/push; wait or coalesce so at most one critical section runs, then the winner (or waiter) publishes
  from current document-store state. Prefer not burning Celery retries solely on self-inflicted push races.
- **C:** Harvest-scoped `POST /v3/harvests/{id}/arcs` MUST reject when the harvest is not `RUNNING` with HTTP
  `409 Conflict` (clear cut-off relative to finalize enqueue on `COMPLETED`). Identical-content retry rules for
  `RUNNING` harvests unchanged.
- **Not in this change:** CouchDB re-read after clone (#348 B); PG migration (#590); lifecycle publish gate (#340).

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `harvest-arc-upload`: Require harvest `RUNNING` before accepting ARC submit; non-`RUNNING` → `409`.
- `harvest-manager`: Document finalize single-flight / coalesce expectations for same-RDI overlapping tasks (alongside
  existing enqueue-on-`COMPLETED` rules).
- `arc-store`: Strengthen consolidated `finalize` concurrency: single-flight critical section per RDI (ephemeral clones
  remain; last-successful-push retained).

## Impact

- API: `submit_arc_in_harvest` status gate; OpenAPI/`ConflictError` messaging.
- Worker: `finalize_catalog` Celery task / `ArcManager.finalize_catalog` / consolidated store — distributed or
  process-safe per-RDI lock.
- Clients: must not submit harvest ARCs after complete/cancel/fail; re-complete still re-enqueues finalize.
- Tests: harvest submit matrix by status; finalize overlap / lock unit tests.
- Orthogonal to #590 (PG): A+C are not throwaway before document-store cutover.
