# Consolidated Git ArcStore — Proposal

## Why

Advanced middleware persists each ARC as its own Git project, while
[m4.2_basic_middleware](https://github.com/fairagro/m4.2_basic_middleware) writes
**one shared Git repository** with **one consolidated JSON file per RDI** (array
of Schema.org `Dataset` objects) into repos such as
[fairagro/middleware_repo](https://github.com/fairagro/middleware_repo). Operators
need Basic-compatible catalog output from Advanced without a second
“CatalogStore” abstraction or `if catalog else arc_store` branching in
callers. Tracked in
[#319](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/319).

## What Changes

- Extend the `ArcStore` port with an optional **`finalize`** operation (default
  no-op on `GitRepo` / `GitlabApi`) so orchestrators stay backend-agnostic.
- Add a **consolidated Git** `ArcStore` implementation selected by config
  (`arc_store.type`, with legacy top-level keys kept working but obsolete):
  - Harvest ARC uploads write **only to CouchDB** (existing content-hash path).
    **No per-ARC Celery Git sync** for this backend — CouchDB already holds the
    authoritative ARC bodies.
  - On harvest `COMPLETED`, **one** finalize task calls `finalize(rdi=…)` and
    rebuilds `{rdi}.json` from **all** current CouchDB ARC documents for that
    RDI, then commit/push to a **separately configured** shared remote (skip
    push when file bytes already match). Not Basic’s `middleware_repo`.
- Produce a **byte-stable** consolidated JSON-LD file: identical logical ARC
  set → identical file bytes across harvests (deterministic ordering,
  canonical JSON serialization, no build-time timestamps injected at catalog
  build).
- Extract Schema.org `Dataset` records from stored ARC RO-Crate content (no
  parallel raw Schema.org upload).
- When the consolidating backend is configured, **reject** standalone
  ARC create on `/v1/arcs`, `/v2/arcs`, and `/v3/arcs` (harvest-scoped product cut).
- Document output shape vs Basic; v1 is one file per configured RDI name
  (Basic `openagrar_*` / `publisso_*` special cases deferred).
- **Non-goals:** dual-write with per-ARC GitLab; CouchDB dirty-marker
  documents; per-ARC Git worker tasks for the consolidated backend; sharing
  Basic’s production remote; moving content-hash into the worker;
  bit-identical Basic jq-merge splits; replacing DataHUB.
- Issue #319 open questions are answered explicitly in `design.md`.

## Capabilities

### New Capabilities

- (none — behaviour stays under `arc-store` plus caller wiring)

### Modified Capabilities

- `arc-store`: Consolidated Git backend; harvest-end `finalize(rdi=…)` rebuilds
  byte-stable `{rdi}.json` from CouchDB; no dirty-marker staging;
  `finalize` no-op on existing backends; skip per-ARC Git sync when this
  backend is selected; `arc_store.type` preferred over obsolete top-level keys.
- `harvest-manager`: On harvest `COMPLETED`, enqueue catalog `finalize` for
  the harvest RDI (async worker task; observable flush events).
- `arc-upload`: When consolidating store is configured, standalone ARC create
  MUST fail fast with a client error (4xx).

## Impact

- **Code:** `middleware/api/.../arc_store/` (new implementation + port method),
  factory/`Config` (`arc_store.type` + deprecated legacy keys),
  harvest-complete → finalize task (not per-ARC sync), standalone ARC create guard,
  catalog flush events/metrics.
- **Specs:** deltas under this change; main specs after archive; Spec-to-Code
  mapping in `AGENTS.md`.
- **Ops:** Configurable catalog remote (Advanced-owned; not Basic’s
  `middleware_repo`); migrate operators from top-level store keys to
  `arc_store.type`. Operator notes: one backend per deployment (no dual-write);
  `{rdi}.json` only in v1; CouchDB ARC bodies are the catalog source (no
  dirty markers); ephemeral Git clone per finalize (no shared local working
  copy).
- **Issue:** Implements
  [#319](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/319).
