# Adopt Devinfra Wave B — Tasks

## 1. Sync from pinned Devinfra SHA

- [x] 1.1 Record pin `a9740d119d0fbe96a813650121db2fab7b2e6136` for the adopt PR
- [x] 1.2 Copy allowlisted Wave B paths (Dockerfile, quality scripts/hooks, fragments,
      versions.env, DX docs, `synced-paths.yaml`, product-app base, package.json/lock,
      verbatim `.pre-commit-config.yaml` + `.vscode/settings.json`)
- [x] 1.3 Refresh allowlisted policy/skills that reference `synced-paths.yaml`
- [x] 1.4 Remove obsolete `docs/synced-paths.global.md`

## 2. Product overlays (exclude / ownership gaps only)

- [x] 2.1 Thin `.devcontainer/devcontainer.json` (name, workspaceFolder, volumes, PATH,
      postCreate → synced script, postStart → bashrc helper)
- [x] 2.2 Product `.devcontainer/docker-compose.yml` bind path + build-args parity
- [x] 2.3 Update `AGENTS.md` for fragments, hooks, golden rule, stubs/`MYPYPATH`
- [x] 2.4 Product CI `reusable-code-quality.yml` → fragments + `MYPYPATH=stubs:…`
- [x] 2.5 Product `load-env.sh` / `setup-bashrc-load-env.sh` / `install-dev-hooks.sh`
      (until #58 / repair)
- [x] 2.6 Add `update-apk-dependencies.sh` (default `Dockerfile.api`, until #68)

## 3. Quality config migration + LFS removal

- [x] 3.1 Strip `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` from root `pyproject.toml`
- [x] 3.2 Remove Git LFS DX (`setup-git-lfs.sh`, LFS hooks, `.gitattributes` sql LFS)
- [x] 3.3 Keep allowlisted pre-commit/settings **verbatim** (no MYPYPATH in YAML; #63)

## 4. Stubs / typing parity

- [x] 4.1 Add `stubs/arctrl` + `stubs/fable_library` + README (until #67)
- [x] 4.2 Add `pyrightconfig.json` with `stubPath` + product `extraPaths` (until #64)
- [x] 4.3 Drop `# type: ignore[import-untyped]` on arctrl/fable imports
- [x] 4.4 Fix test helper imports (`client_test_support` in `tests/unit/`) and
      tools (`rocrate2arc` top-level optional fable import)

## 5. Verify

- [x] 5.1 Focused pytest (api_client unit) + mypy with `MYPYPATH=stubs:…`
- [x] 5.2 Dev Container rebuild smoke (`postCreate`, `quality-check` after Node globals)
      — Node 22.23.2 + prettier/markdownlint globals OK; after
      `uv sync --dev --all-packages` + `MYPYPATH` (now in product `load-env.sh`),
      `SKIP=check-yaml,markdownlint ./scripts/quality-check.sh` green (upstream
      [#59](https://github.com/fairagro/m4.2_middleware_devinfra/issues/59) /
      [#63](https://github.com/fairagro/m4.2_middleware_devinfra/issues/63))
- [x] 5.3 Draft PR: `Fixes #367`, pinned SHA, link upstream #56–#69 as needed
      — https://github.com/fairagro/m4.2_advanced_middleware_api/pull/377
