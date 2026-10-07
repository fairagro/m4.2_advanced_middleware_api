# Tasks

## 1. Package scaffold

- [ ] 1.1 Create `middleware/arc_validation/` with `pyproject.toml` (`fairagro-middleware-arc-validation`, hatch-vcs,
      `arctrl` dependency, console script `fairagro-arc-validate`), `src/middleware/arc_validation/`, `tests/unit/`, and
      `README.md`; verify `uv sync --dev --all-packages` resolves the new member
- [ ] 1.2 Add the package to root `pyproject.toml` workspace members / `[tool.uv.sources]`, extend `extraPaths` /
      `MYPYPATH` / workflow `mypy_path` / pylint `--source-roots` / `.devcontainer/product.env` for the new src+tests
      roots; verify `uv run python -c "import middleware.arc_validation"` works after sync

## 2. Core library

- [ ] 2.1 Implement `ArcExportResult` (ok, exit_code, stdout, stderr, cause_excerpt) and `write_arc_scaffold` using
      ARCtrl (`from_rocrate_json_string` + `Write`); verify unit tests cover success path and write failure mapping
- [ ] 2.2 Implement `run_arc_export` (Docker `run --rm`, mount ARC dir, default image
      `ghcr.io/nfdi4plants/arc-export:main`, default formats `rocrate-metadata-lfs` / `isa-json` / `summary-markdown`,
      env override for image); verify unit tests mock subprocess and assert argv/image/formats
- [ ] 2.3 Implement `validate_rocrate` (temp dir → write → export → cleanup) and cause-excerpt extraction; verify unit
      tests for pass, Docker fail with excerpt, and ARCtrl write failure → `ok=False`
- [ ] 2.4 Implement CLI `fairagro-arc-validate` (path arg, exit 0 / non-zero, stderr cause); verify unit test of
      argument parsing / exit codes with mocked `validate_rocrate`

## 3. Optional live Docker + docs mapping

- [ ] 3.1 Add `@pytest.mark.requires_docker` integration test skipped by default; verify
      `uv run pytest -m "not requires_docker" middleware/arc_validation/tests` passes without Docker
- [ ] 3.2 Document install/usage/image override in package README; add Spec-to-Code row in `AGENTS.md` for
      `openspec/specs/arc-export-validation/` → `middleware/arc_validation/`; verify README commands match the public
      API names

## 4. Release / ci-cd wiring

- [ ] 4.1 Extend release/PyPI publish configuration so `middleware/arc_validation` builds and publishes as
      `fairagro-middleware-arc-validation` alongside shared and api-client; verify workflow/config lists all three
      package paths/names
- [ ] 4.2 Sync delta intent into apply notes: after merge/archive, main `openspec/specs/ci-cd/` and new
      `openspec/specs/arc-export-validation/` MUST match this change; verify change artifacts stay coherent with
      implemented paths

## 5. Integration check

- [ ] 5.1 Run targeted unit tests for the new package plus `./scripts/quality-check.sh` (or equivalent scoped quality)
      and verify no regressions on existing middleware packages
