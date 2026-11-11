# Tasks

## 1. Port types (shared base + role ABCs)

- [ ] 1.1 Split `middleware/api/src/middleware/api/arc_store/__init__.py` into `_ArcStoreBase` / `ArcStoreBase`
      (lifecycle only), narrow `ArcStore` (per-ARC CRUD wrappers, no `finalize`), and add `ConsolidatedArcStore`
      (`finalize` wrappers only); export new types; verify
      `uv run mypy --config-file mypy.ini middleware/api/src/middleware/api/arc_store/__init__.py` type-checks the
      module
- [ ] 1.2 Point `GitRepo` at `ArcStore` and `ConsolidatedGitArcStore` at `ConsolidatedArcStore`; delete catalog CRUD
      stubs and any per-ARC `finalize` reliance; verify
      `uv run ruff check --config ruff.toml middleware/api/src/middleware/api/arc_store/` is clean
- [ ] 1.3 Update `test_arc_store.py` (remove default-finalize no-op; cover role surfaces / wrappers); verify
      `uv run pytest middleware/api/tests/unit/test_arc_store.py -v` passes

## 2. Dual-slot typing at wiring

- [ ] 2.1 Type factory / `ArcManager` / `BusinessLogic` / health so `store: ArcStore` and
      `consolidated_store: ConsolidatedArcStore | None`; verify
      `uv run mypy --config-file mypy.ini middleware/api/src/middleware/api/business_logic/ middleware/api/src/middleware/api/arc_store/`
      reports no new errors on those paths
- [ ] 2.2 Grep call sites for cross-role usage (`\.finalize(` on per-ARC mocks, CRUD on consolidated) and fix tests /
      helpers; verify `uv run pytest middleware/api/tests/unit/ -k "arc_store or arc_manager or factory or health" -v`
      (or equivalent focused set) passes
- [ ] 2.3 Add or extend a focused unit test that factory/wiring accepts matching ports only (sync vs finalize); verify
      that test passes under `uv run pytest`

## 3. Quality gate

- [ ] 3.1 Run format/lint on touched Python: `uv run ruff format --config ruff.toml middleware/api/` and
      `uv run ruff check --config ruff.toml middleware/api/` — both clean for edited files
- [ ] 3.2 Run broader regression:
      `uv run pytest middleware/api/tests/unit/test_arc_store.py middleware/api/tests/unit/test_consolidated_git*.py middleware/api/tests/unit/test_git_repo*.py -v`
      (adjust globs to existing test modules) — all pass

## Workflow follow-up

- After apply + user commits/push: draft PR with `Fixes #615`.
- Archive this change after review requirements are satisfied (`/opsx-archive` / issue-fixer last `go`).
