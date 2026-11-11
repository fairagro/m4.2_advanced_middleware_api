# Tasks

## 1. Shared identity + Protocol

- [ ] 1.1 Move `calculate_arc_id` into `middleware.shared` (new helper module), point `api` and `api_local_offline` at
      it, delete duplicates, and verify existing identity/hash unit tests still pass via `uv run pytest` on the touched
      packages
- [ ] 1.2 Add the harvest/ARC lifecycle **Protocol** (and any shared result/DTO helpers that avoid `api` types) under
      `middleware.shared`, with a focused unit test that a minimal stub satisfies the Protocol for typing/runtime checks

## 2. New `api_v3` package + routers

- [ ] 2.1 Scaffold workspace package `fairagro-middleware-api-v3` at `middleware/api_v3` (pyproject, hatch, uv workspace
      member, FastAPI + shared deps) and verify `uv sync --dev --all-packages` installs it
- [ ] 2.2 Implement shared FastAPI routers for the MVP lifecycle surface and a mount helper; verify a tiny FastAPI app
      with a stub port exposes the expected paths/methods in a unit test under `middleware/api_v3/tests/`
- [ ] 2.3 Update `.importlinter` and `openspec/principles.md` for `api_v3` edges; verify
      `./scripts/run-import-linter.sh` passes

## 3. Offline adapter + mount

- [ ] 3.1 Implement the offline Protocol adapter (filesystem ARC write + in-memory harvest) and mount shared routers
      from `api_local_offline` app factory; remove hand-rolled lifecycle `add_api_route` duplicates and local
      `arc_id.py`
- [ ] 3.2 Extend/adjust `middleware/api_local_offline/tests` so the ApiClient harvest lifecycle still completes and ARC
      files land on disk; verify with `uv run pytest middleware/api_local_offline/tests/`

## 4. Production adapter + mount

- [ ] 4.1 Implement the production Protocol adapter over existing HarvestManager/ArcManager (+ auth/RDI deps as today)
      and mount shared routers from the production FastAPI app for the MVP surface; remove overlapping local route defs
- [ ] 4.2 Run focused production API unit/integration tests for harvest/ARC upload paths and verify they pass
      (`uv run pytest` on the affected `middleware/api/tests` modules)

## 5. Contract smoke

- [ ] 5.1 Add a contract/smoke test that production and offline apps expose the same MVP lifecycle paths/methods (and
      shared `response_model` where attached); verify it fails if either app omits a path and passes on the dual mount
- [ ] 5.2 Update `AGENTS.md` Spec-to-Code Mapping for `v3-http-contract` / package paths; verify the documented entry
      matches the landed modules

## Workflow follow-up

- Archive the change after review requirements are satisfied (`/opsx-archive` / issue-fixer last `go`).
- Follow-up (linked): remaining `/v3` surfaces (list harvests, deprecated aliases, full system routers) onto the shared
  package if still desired.
