# Adopt Devinfra Wave B — Proposal

## Why

Shared Devinfra Wave B (Dev DX: quality scripts/hooks, Dev Container base, Python
quality fragments, versions.env) is landed upstream and was piloted on the harvester
([#168](https://github.com/fairagro/m4.2_middleware_harvester/issues/168) /
[PR #180](https://github.com/fairagro/m4.2_middleware_harvester/pull/180)). This repo
still uses product-local quality config in `pyproject.toml`, an older Dev Container
image, LFS-era git hooks, and drifted quality scripts. Issue
[#367](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/367) asks to
adopt Wave B without hand-editing synced Devinfra paths (golden rule / [#57](https://github.com/fairagro/m4.2_middleware_devinfra/issues/57)).

**Pinned Devinfra SHA for this adopt:** `a9740d119d0fbe96a813650121db2fab7b2e6136`
(document the same value in the adopt PR description).

## What Changes

- Sync Wave B allowlisted paths from Devinfra at the pinned SHA: Dev Container
  Dockerfile, quality runners (`quality-*.sh`, CST helper, `setup-git-hooks.sh`,
  `git-hooks/pre-push`), `devcontainer-post-create.sh`, `load-versions-env.sh`,
  quality fragments (`ruff.toml`, `mypy.ini`, `.pylintrc`, `.bandit`, markdownlint,
  prettier), `versions.env` / `.python-version`, DX docs (`quality.md`,
  `devcontainer.md`, `conventions.md`, `ci.md`, `sync.md`, …),
  `docs/synced-paths.yaml` (replaces obsolete `synced-paths.global.md`),
  `docker/Dockerfile.product-app.base`, Node `package.json` / lock for markdown tooling,
  and refresh of Wave A allowlisted policy/skills that now reference the YAML allowlist.
- Adopt `.pre-commit-config.yaml` and `.vscode/settings.json` **verbatim** (on
  allowlist — no product re-patch; path overlays via CI/`MYPYPATH` env per [#63](https://github.com/fairagro/m4.2_middleware_devinfra/issues/63) / [#57](https://github.com/fairagro/m4.2_middleware_devinfra/issues/57)).
- Thin product overlays only where YAML `exclude` / ownership issues allow:
  `.devcontainer/devcontainer.json`, `docker-compose.yml`, `AGENTS.md`, product CI
  `reusable-code-quality.yml`, `scripts/load-env.sh`, hook-repair helpers,
  `setup-bashrc-load-env.sh` (until [#58](https://github.com/fairagro/m4.2_middleware_devinfra/issues/58)),
  `update-apk-dependencies.sh` (until [#68](https://github.com/fairagro/m4.2_middleware_devinfra/issues/68)).
- Drop Git LFS from Dev DX (remove `setup-git-lfs.sh`, LFS hooks, `.gitattributes`
  `*.sql` LFS tracking) — this product does not need LFS.
- Strip duplicated `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` from root
  `pyproject.toml`; point tools at fragments.
- Add fleet `stubs/` (`arctrl`, `fable_library`) + `pyrightconfig.json` until
  [#67](https://github.com/fairagro/m4.2_middleware_devinfra/issues/67) / [#64](https://github.com/fairagro/m4.2_middleware_devinfra/issues/64);
  drop `# type: ignore[import-untyped]` on covered imports; keep `MYPYPATH=stubs:…`
  in product CI/docs (not in synced pre-commit YAML).
- Small test/tool cleanups surfaced by the new gates (relative test helper imports,
  top-level optional fable import).

**Out of scope (Wave C / upstream):** Bake/`docker-bake.hcl` product image wiring,
CST bake targets, waiting for first sync PR from Devinfra [#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13),
patching shared post-create for `uv sync --dev --all-packages` (track [#56](https://github.com/fairagro/m4.2_middleware_devinfra/issues/56)).

## Capabilities

### New Capabilities

_None — `skip_specs: true` (tooling/docs adopt; no domain requirement deltas)._

### Modified Capabilities

_None._

## Impact

- Dev Container rebuild required (new Dockerfile / toolchain pins / Node globals).
- Local + CI quality commands use `ruff.toml` / `mypy.ini` / `.pylintrc` instead of
  root `pyproject` tool tables; commit-stage hooks follow shared pre-commit YAML.
- Agents must not hand-edit allowlisted paths; use overlays or Devinfra issues
  (#56–#69 family, esp. #57, #63, #65).
- No HTTP API or CouchDB/Celery behaviour change.
