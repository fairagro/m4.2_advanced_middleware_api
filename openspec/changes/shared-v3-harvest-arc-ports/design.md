# Design

## Context

See `proposal.md` — Why. Today production mounts `middleware.api.api.v3.{harvests,arcs}` against `BusinessLogic`;
offline registers overlapping paths in `api_local_offline.app` with soft semantics and dict bodies. `shared` already
owns `api_models.v3` and must stay free of FastAPI (principles + import-linter). `calculate_arc_id` exists in both
`middleware.api.utils` and `middleware.api_local_offline.arc_id`.

## Goals / Non-Goals

**Goals:**

- One FastAPI route surface for the ApiClient harvest lifecycle, mounted by both apps.
- One Protocol for harvest/ARC ops; adapters keep semantics separate.
- Single `calculate_arc_id` in `shared`.
- Offline still installs without package `api`.

**Non-Goals:**

- Sharing handler _bodies_ that force production 409/identity onto offline.
- Migrating list-harvests, deprecated aliases, or full `/v3` system routers in this change.
- Changing production HTTP status contracts in `arc-upload` / `harvest-arc-upload`.

## Decisions

1. **Package split (lock-in 2b)**
   - **Protocol + `calculate_arc_id`** → `middleware.shared` (no FastAPI).
   - **Router factories** → new workspace package `fairagro-middleware-api-v3` at `middleware/api_v3`, depends on
     `fairagro-middleware-shared` + FastAPI.
   - **Why not all in `shared`:** would pull FastAPI into every `shared` consumer (`api_client`, etc.).
   - **Why not all in a new package:** Protocol and identity hash should stay usable without FastAPI (tests, workers).

2. **MVP route set (lock-in B)** Shared routers cover: create/get/patch harvest, submit ARC in harvest, complete
   harvest, standalone `POST /v3/arcs`, and a minimal successful liveness probe. Production keeps existing modules for
   deferred endpoints until a follow-up; offline drops hand-rolled registration for the MVP set.

3. **Dependency injection** Routers take the Protocol via FastAPI `Depends` with an app-level override / factory
   supplied at mount time. Production adapter wraps existing managers + RDI auth. Offline adapter wraps in-memory
   harvest map + filesystem store. Soft vs strict HTTP mapping lives in the adapter, not in shared routers.

4. **`calculate_arc_id`** Move implementation to `middleware.shared` (e.g. identity helper module). `api` and offline
   import from there; delete duplicates. Behavior unchanged (strip-only rules already shared by call sites).

5. **Import graph** Extend `.importlinter` / `principles.md`: `api` and `api_local_offline` may → `api_v3` → `shared`;
   `api_v3` ↛ `api`; `shared` ↛ `api_v3`|`api`|`api_client`. Add `middleware.api_v3` to root_packages / acyclic_siblings
   as needed.

6. **Contract smoke** One test module (prefer under `api_v3` or a small shared test helper) that introspects both
   FastAPI apps’ route tables for path + methods (+ `response_model` where attached) for the MVP surface.

## Risks / Trade-offs

- **[Risk]** Partial dual registration during migration (prod still has old routers + new). → **Mitigation:** replace
  prod harvest/ARC MVP routers in the same change; keep deferred endpoints only in prod-local modules.
- **[Risk]** Protocol too wide and leaks CouchDB types into offline. → **Mitigation:** port methods use shared v3 DTOs /
  plain result types only.
- **[Risk]** New package packaging/CI friction. → **Mitigation:** mirror `api_local_offline` workspace member pattern;
  update `uv` workspace + quality path overlays.
- **[Trade-off]** Two packages to touch for HTTP changes vs one heavy `shared`. Accepted to keep `shared` light.

## Migration Plan

1. Land `shared` Protocol + `calculate_arc_id`; update `api`/offline imports.
2. Add `api_v3` package with routers + empty/test adapter stubs.
3. Offline mounts shared routers; remove duplicate routes/`arc_id.py`.
4. Production mounts shared routers for MVP surface; delete overlapping local route defs.
5. Contract smoke + existing unit/integration suites green.
6. Rollback: revert the PR; no on-disk config migration.

## Open Questions

None for this MVP slice; deferred endpoints are an explicit follow-up.
