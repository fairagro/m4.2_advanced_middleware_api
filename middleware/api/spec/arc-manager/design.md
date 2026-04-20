# ARC Ingestion Pipeline — Design

## Module Overview

`ArcManager.create_or_update_arc` (in `business_logic/arc_manager.py`) is the
shared ingestion entry point. It is invoked by two HTTP endpoints — both
resolve their preconditions (authorization, harvest lookup) before calling it,
so the method itself is HTTP-agnostic and safe to call from a worker context.

```text
arc-upload/               arc-harvest-upload/
    │                           │
    └─────────────┬─────────────┘
                  ▼
    ArcManager.create_or_update_arc(rdi, arc, client_id, harvest_id=None)
        ├─→ extract_identifier(arc)              ← validation
        ├─→ DocumentStore.store_arc(...)         ← fast CouchDB write
        ├─→ DocumentStore.increment_harvest_statistics(...)  ← if harvest_id
        └─→ TaskDispatcher.dispatch_sync_arc(...)            ← if new or changed

ArcManager also owns the worker-side counterpart (separate spec: arc-store/):
    └─→ ArcManager.sync_to_gitlab(rdi, arc)
```

## Key Decisions

1. **Two-phase ingestion: CouchDB first, GitLab async**
   — GitLab operations can take seconds per ARC. Making the API caller wait
   would cap throughput unacceptably. CouchDB writes are fast; the caller
   gets a response immediately while GitLab sync runs in the background via
   Celery.

2. **Single method handles both standalone and harvest-context callers**
   — The only difference between the two call sites is the source of `rdi`
   and the presence of `harvest_id`. Both differences are resolved by the
   caller before reaching `ArcManager`, so one method covers both. This keeps
   the CouchDB write and Celery dispatch logic in a single place.

3. **Mode enforcement via `TaskDispatcher` presence**
   — `ArcManager` is instantiated differently for API and worker processes.
   Rather than subclassing, a nullable `_dispatcher` field enforces context at
   runtime: API mode requires a dispatcher; worker mode must not have one.
   Calling `create_or_update_arc` without a dispatcher raises `BusinessLogicError`
   immediately, making accidental misuse visible during development.

4. **`identifier` extracted once before storage**
   — `extract_identifier` traverses the RO-Crate JSON graph. The extracted
   value is passed directly into `DocumentStore.store_arc`, avoiding a second
   traversal inside the store.

5. **Idempotency via content hash**
   — `DocumentStore.store_arc` computes a hash of the serialized ARC and sets
   `has_changes = False` when the hash matches the stored document. This
   prevents redundant Celery tasks and GitLab commits on re-submission of
   unchanged ARCs, making the pipeline safe to call repeatedly.

6. **Harvest statistics incremented unconditionally when `harvest_id` is set**
   — The counter is incremented regardless of whether the ARC content changed.
   A re-submitted unchanged ARC still counts as a processed dataset from the
   harvest's perspective. This keeps the counter semantics simple: one
   increment per ARC received, not per ARC written.

7. **ARC crosses process boundary as a `dict`, not an `ARC` object**
   — ARCtrl objects carry .NET interop state and must not be pickled. The
   ingestion pipeline dispatches the raw `dict` to Celery; the worker
   re-parses it with `ARC.from_rocrate_json_string`. This avoids serialization
   errors and keeps the Celery task payload simple JSON.
