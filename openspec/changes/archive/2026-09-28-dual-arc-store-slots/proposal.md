## Why

Production needs **GitRepo** (per-ARC GitLab projects) and **ConsolidatedGit** (shared RDI `{rdi}.json` catalog) **at
the same time**. Today configuration and OpenSpec allow exactly one ArcStore backend and treat dual-write as out of
scope, so operators must choose between the main store and the catalog. Issue #517 locks a dual-slot contract after
explore.

## What Changes

- **BREAKING:** Replace “exactly one ArcStore backend” with two config roles:
  - **required** `arc_store` — per-ARC only; backend selected by nested `git_repo:` or deprecated `gitlab_api:` (no
    `type` field); catalog settings under `arc_store` are **invalid**
  - **optional** `consolidated_store` — catalog only (`consolidated_git:` settings; slot name selects the role)
- **BREAKING:** Drop obsolete top-level `git_repo` / `gitlab_api` / `consolidated_git` keys (no compat window). Helm
  values, config-secret, and docs migrate in this change.
- Per-slot optional `git:` blocks sharing the same `GitCliSettings` type (no single top-level merge into both).
- Factory / `ArcManager` hold two references; call **only** role-appropriate operations (sync → `arc_store`; finalize /
  `CATALOG_PUSH_*` → `consolidated_store` when present).
- **Drop** `supports_standalone_upload` gating: standalone `/v1|/v2|/v3/arcs` always accepted; persist via `arc_store`
  only; catalog skipped. Document on Pydantic models (Swagger).
- Health: when consol. configured and git-backend checks enabled, expose both `git_backend` and a consolidated key;
  aggregate unchanged (`any` false → ERROR). No extra flag to disable consol. health.
- No multi-store failure policy / no peer array; no cross-store ordering barrier (catalog reads CouchDB; sync and
  finalize remain eventually consistent).
- Keep one `ArcStore` ABC for now (#518 Discussion). Keep deprecated `gitlab_api` until #182.
- Out of scope: #519 (FAILED after Celery exhaustion), #518 ABC split, #182 GitlabApi removal.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Dual-slot config; drop “exactly one” / dual-write out-of-scope; drop top-level legacy; role-based ops;
  health keys; remove standalone-reject-when-consolidated requirement ownership where it lives here vs upload specs
- `arc-upload`: Standalone always allowed; documents per-ARC-only publish; remove reject-when- consolidated requirement
- `arc-manager`: Two store references; role-specific sync/finalize/events; drop standalone gate
- `harvest-manager`: Finalize enqueue only when `consolidated_store` configured; catalog events only then

## Impact

- Code: `arc_store/{factory,resolution,arc_store_config}.py`, API/worker `config.py`, `BusinessLogicFactory`,
  `ArcManager`, `ApiHealthService`, Helm chart values/config-secret/NOTES
- Deployments using top-level store keys or `arc_store.type: consolidated_git` alone must migrate
- OpenSpec main specs listed above; related tests and Swagger descriptions
- Related issues: #517 (this), #518, #519, #182, #334 (legacy path largely subsumed)
