# Design

## Context

See proposal.md — Why. Today: every harvest `COMPLETED` (including idempotent re-complete) enqueues `finalize_catalog`
for the RDI; workers may overlap; consolidated finalize uses ephemeral clones and last-successful-push. Harvest ARC
submit does not check harvest status beyond existence/auth.

Constraints: no new Redis dependency solely for this change if avoidable; Celery broker is RabbitMQ; document store is
still CouchDB until #590; multi-worker Celery is normal.

## Goals / Non-Goals

**Goals:**

- At most one finalize critical section (clone → rebuild → push) per RDI at a time across workers.
- Clear harvest cut-off: no harvest-scoped ARC ingest after terminal status.
- Preserve re-complete → re-enqueue finalize for recovery after dispatch failure.

**Non-Goals:**

- Strong distributed locking for DataHub Git beyond single-flight (no change to last-successful-push model).
- Re-read document store after clone (#348 B).
- PG migration (#590) or lifecycle publish gate (#340).
- Changing standalone `POST /v3/arcs` (no harvest).

## Decisions

### D1: Single-flight lock in the worker finalize path (not enqueue drop)

**Choice:** Acquire a per-RDI lock inside `finalize_catalog` / `ArcManager.finalize_catalog` (or consolidated store
`finalize`) around the heavy work. Concurrent tasks for the same RDI **wait** for the lock (bounded), then run (or no-op
if catalog bytes unchanged), so a late enqueued task still sees document-store state after earlier harvests finished
writing.

**Alternatives considered:**

| Option                             | Why not (for MVP)                                                         |
| ---------------------------------- | ------------------------------------------------------------------------- |
| Drop enqueue if “pending”          | Celery inspect is unreliable; risk missing finalize after failed dispatch |
| Per-RDI Celery queue concurrency=1 | Ops/Helm complexity; still need routing keys                              |
| Redis `celery-once`                | New infra dependency                                                      |
| Fire-and-forget skip if lock held  | Can miss ARCs committed between first task start and second enqueue       |

**Lock backend (implementation preference order):** (1) document-store claim document / conditional write keyed by RDI
if cheap with existing CouchDB helpers; (2) filesystem lock under a shared worker volume only if product already
guarantees one node (insufficient for multi-replica); (3) small dedicated lock helper. Exact backend is an apply-time
choice as long as it is safe under multi-worker Celery.

### D2: Lock failure / timeout

If the lock cannot be acquired within a bounded wait, treat as **transient** (Celery retry) rather than permanent
failure — avoids silent catalog lag. Do not count “lost push race with self” as the primary retry reason once
single-flight is in place; existing non-fast-forward from external writers may still retry.

### D3: Harvest submit requires `RUNNING`

**Choice:** In `submit_arc_in_harvest` (after load harvest, before `create_or_update_arc`), if
`harvest.status != RUNNING` → `ConflictError` → HTTP `409` with a message that includes the current status. Do **not**
append harvest per-item ARC errors for this gate (it is harvest-lifecycle, not ARC identity/content conflict).

**Alternatives:** `400`/`422` — weaker for clients that already treat `409` as “do not retry as success”; `403` — wrong
auth semantics.

### D4: Unchanged identical-content retries

Only apply the `RUNNING` gate; existing identical-content `200` / content-conflict `409` rules for `RUNNING` harvests
stay as in `harvest-arc-upload`.

## Risks / Trade-offs

- [Lock wait increases finalize latency under storms] → Acceptable vs push churn; monitor wait time.
- [Lock backend unavailable] → Fail transient → retry; document ops dependency.
- [Clients submit after complete today] → **BREAKING** for that misuse path only; intentional cut-off — document in
  OpenAPI and harvest-client notes if needed.
- [Waiter runs after first finalize and finds identical bytes] → No-op push (already required) — safe.

## Migration Plan

Deploy API + worker together for C (API gate) and A (worker lock). Rollback: revert gate (late submits work again);
revert lock (storms return). No data migration.

## Open Questions

None that block specs — lock backend chosen at apply within D1 preference order.
