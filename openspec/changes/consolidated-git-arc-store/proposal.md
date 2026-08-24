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
  (mutually exclusive with `git_repo` / `gitlab_api`):
  - `create_or_update` **stages** work for an ARC/RDI via a **durable dirty
    set in CouchDB** (markers only — not a second copy of ARC bodies; bodies
    already live in the document store). No full RDI file rewrite on every ARC
    when avoidable;
  - `finalize` rebuilds `{rdi}.json` from current CouchDB ARC documents for
    that RDI, commits/pushes to the shared remote, and clears dirty markers.
- Produce a **byte-stable** consolidated JSON-LD file: identical logical ARC
  set → identical file bytes across harvests (deterministic ordering,
  canonical JSON serialization, no build-time timestamps or other volatile
  fields injected at catalog build).
- Extract Schema.org `Dataset` records from stored ARC RO-Crate content (no
  parallel raw Schema.org upload).
- Wire harvest completion to invoke `finalize` for the harvest’s RDI.
- When the consolidating backend is configured, **reject** standalone
  `POST /v3/arcs` (harvest-scoped product cut).
- Document output shape vs Basic; v1 is one file per configured RDI name
  (Basic `openagrar_*` / `publisso_*` special cases deferred).
- **Non-goals:** dual-write with per-ARC GitLab; moving content-hash into the
  worker; bit-identical Basic jq-merge splits; replacing DataHUB; using
  CouchDB as a full RO-Crate staging dump (bodies stay the normal ARC
  documents).

## Capabilities

### New Capabilities

- (none — behaviour stays under `arc-store` plus caller wiring)

### Modified Capabilities

- `arc-store`: Consolidated Git backend; CouchDB dirty-marker staging; stage
  vs finalize; byte-stable `{rdi}.json` publish; extraction; `finalize` no-op
  on existing backends.
- `harvest-manager`: On successful harvest completion, invoke ArcStore
  `finalize` for the harvest RDI (async worker task; observable flush events).
- `arc-upload`: When consolidating store is configured, standalone ARC create
  MUST fail fast with a client error (4xx).

## Impact

- **Code:** `middleware/api/.../arc_store/` (new implementation + port method),
  factory/`Config` mutual exclusivity, `HarvestManager` / worker finalize task,
  `POST /v3/arcs` guard, events/metrics for catalog flush.
- **Specs:** deltas under this change; main specs after archive; Spec-to-Code
  mapping in `AGENTS.md`.
- **Ops:** New config block for shared-repo URL/credentials/path; coexistence
  with Basic writers on the same remote is an operator/race concern (no
  distributed lock in v1).
- **Issue:** Implements
  [#319](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/319).
