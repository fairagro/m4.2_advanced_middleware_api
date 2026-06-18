# ARC Ingestion Pipeline — Design

## Module Overview

`ArcManager.create_or_update_arc` (in `business_logic/arc_manager.py`) is the
shared ingestion entry point. It is invoked by two HTTP endpoints — both
resolve their preconditions (authorization, harvest lookup) before calling it,
so the method itself is HTTP-agnostic and safe to call from a worker context.

```text
arc-upload/               harvest-arc-upload/
    │                           │
    └─────────────┬─────────────┘
                  ▼
    ArcManager.create_or_update_arc(rdi, arc, client_id, harvest_id=None)
        ├─→ RoCratePayload validation              ← HTTP or parse_rocrate
        ├─→ DocumentStore.store_arc(...)         ← fast CouchDB write (+ harvest metadata if harvest_id)
        └─→ TaskDispatcher.dispatch_sync_arc(...)            ← if new or changed

ArcManager also owns the worker-side counterpart (separate spec: `arc-store/`):
    └─→ ArcManager.sync_to_gitlab(rdi, arc)
            ├─→ parse_rocrate (lightweight re-validation of queued JSON)
            ├─→ ARC.from_rocrate_json_string(...)   ← arctrl parse (worker only)
            └─→ ArcStore.create_or_update(..., rdi=rdi)
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

4. **`identifier` extracted once during RO-Crate validation**
   — `RoCratePayload` (`middleware/shared/api_models/common/rocrate.py`)
   validates the wire format (`@context`, `@graph`, root dataset `./` with
   non-empty `identifier`). Validator functions read `identifier`, `name`, and
   `description` from that root node; other root properties remain in `@graph`
   unchanged. The RoCrate wire contract is documented in `arc-manager/spec.md`.

5. **Idempotency via content hash**
   — `DocumentStore.store_arc` computes a hash of the serialized ARC and sets
   `has_changes = False` when the hash matches the stored document. This
   prevents redundant Celery tasks and GitLab commits on re-submission of
   unchanged ARCs, making the pipeline safe to call repeatedly.

6. **Harvest statistics derived at finalize, not incremented per ARC**
   — `store_arc` stamps harvest context on each ARC document (`last_harvest_id`,
   `first_harvest_id`, `last_changed_harvest_id`). When a harvest transitions to a
   terminal status, `HarvestManager` calls `DocumentStore.get_harvest_statistics`
   to classify submitted ARCs as new, updated, or unchanged. There is no per-ARC
   counter write on the harvest document during ingest.

7. **ARC crosses process boundary as a `dict`, not an `ARC` object**
   — ARCtrl objects carry .NET interop state and must not be pickled. The
   ingestion pipeline dispatches the raw `dict` to Celery; the worker
   re-parses it with `ARC.from_rocrate_json_string`. This avoids serialization
   errors and keeps the Celery task payload simple JSON.

8. **No arctrl parse on the API ingest path**
   — `parse_rocrate` applies only `RoCratePayload` validation (cheap: `@context`,
   `@graph`, root `./`, non-empty `identifier`). `ARC.from_rocrate_json_string`
   is intentionally **not** called in `create_or_update_arc`; that step is
   expensive and runs once in the Celery worker during `sync_to_gitlab`. The API
   writes the JSON to CouchDB and returns immediately.

9. **Display metadata derived inside `GitRepo`, not at ingest time**
   — Human-readable GitLab labels (`name`, `description`, RDI topic) are built
   by ``git_project_metadata_from_arc`` when ``GitRepo`` calls
   ``GitlabGitProvider.ensure_repo_exists``. Ingest (`create_or_update_arc`) does
   not need this metadata because CouchDB stores the full ARC document; only
   ``rdi`` crosses into ``ArcStore`` as middleware context.
