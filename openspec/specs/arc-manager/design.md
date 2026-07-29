# ARC Ingestion Pipeline — Design

## Module Overview

`ArcManager.create_or_update_arc` (in `business_logic/arc_manager.py`) is the shared ingestion entry point. HTTP
endpoints resolve authorization and harvest lookup before calling it, so it is HTTP-agnostic and safe from a worker
context.

```text
arc-upload/               harvest-arc-upload/
    │                           │
    └─────────────┬─────────────┘
                  ▼
    ArcManager.create_or_update_arc(rdi, arc, client_id, harvest_id=None)
        ├─→ RoCratePayload validation              ← HTTP or parse_rocrate
        ├─→ DocumentStore.store_arc(...)            ← fast CouchDB write (+ harvest metadata)
        └─→ TaskDispatcher.dispatch_sync_arc(...)   ← only if new or changed

ArcManager.sync_to_gitlab(rdi, arc)  (see openspec/specs/arc-store/)
    ├─→ parse_rocrate
    ├─→ ARC.from_rocrate_json_string(...)
    └─→ ArcStore.create_or_update(..., rdi=rdi)
```

## Key Decisions

1. **Two-phase ingestion: CouchDB first, GitLab async** — GitLab operations can take seconds. CouchDB writes are fast,
   so the caller receives an immediate response while Celery performs GitLab sync.

2. **One method for standalone and harvest callers** — Callers resolve the RDI and harvest context before invoking the
   method. Shared CouchDB and Celery logic therefore remains in one place.

3. **Mode enforcement through `TaskDispatcher` presence** — API mode requires a dispatcher and worker mode must not have
   one. Calling `create_or_update_arc` without its dispatcher raises `BusinessLogicError`, exposing accidental
   misuse.

4. **Extract `identifier` once during wire validation** — `RoCratePayload` validates `@context`, `@graph`, root `./`,
   and a non-empty `identifier`; validators also read `name` and `description`, leaving other root properties
   unchanged. The contract is in the adjacent `spec.md`.

5. **Content-hash idempotency, including harvest retry** — `DocumentStore.store_arc` marks identical content as
   unchanged, avoiding redundant tasks and commits. In one harvest, same identifier and hash returns `UPDATED`; a
   different hash raises `DuplicateArcError` rather than overwriting.

6. **Derive harvest statistics at finalization** — Storage stamps `last_harvest_id`, `first_harvest_id`, and
   `last_changed_harvest_id`; `HarvestManager` uses `DocumentStore.get_harvest_statistics` at the terminal
   transition. No per-ARC harvest counter writes occur during ingest.

7. **Cross process boundaries as JSON dictionaries** — arctrl objects carry .NET interop state and cannot safely be
   pickled. The worker reparses raw JSON into an ARC.

8. **Do not parse arctrl during API ingestion** — `parse_rocrate` performs only inexpensive wire validation.
   `ARC.from_rocrate_json_string` runs in the Celery worker so the API can store and return promptly.

9. **Derive display metadata in `GitRepo`** — `git_project_metadata_from_arc` derives GitLab labels when `GitRepo` calls
   `GitlabGitProvider.ensure_repo_exists`. Ingest stores the full document and passes only `rdi` as middleware
   context.
