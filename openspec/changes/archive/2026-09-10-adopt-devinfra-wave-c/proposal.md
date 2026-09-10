# Adopt Devinfra Wave C — Proposal

## Why

Shared Devinfra Wave C (reusable CI + Bake product-app layout + Helm reusables) is
landed upstream and piloted on the harvester
([#169](https://github.com/fairagro/m4.2_middleware_harvester/issues/169) /
[PR #181](https://github.com/fairagro/m4.2_middleware_harvester/pull/181)). This repo
still calls local `reusable-{code-quality,check,build,release}.yml`, has no
`docker-bake.hcl`, and keeps a full multi-stage `Dockerfile.api`. Issue
[#368](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/368) asks to
adopt Wave C without hand-editing synced Devinfra paths (golden rule /
[#57](https://github.com/fairagro/m4.2_middleware_devinfra/issues/57)).

## What Changes

- **BREAKING (build):** Devinfra build is Bake-only. Add product-local root
  `docker-bake.hcl` + thin `docker/Dockerfile.api` last stage; keep synced
  `docker/Dockerfile.product-app.base` verbatim.
- Point `feature-pull-request` / `pre-release` / `release` at Devinfra
  `reusable-{code-quality,build,release}` (`@main`, SHA-pin code-quality while
  [#72](https://github.com/fairagro/m4.2_middleware_devinfra/pull/72) is unmerged).
- Pass product overlays via `with:` (`mypy_path`, `pylint_source_roots`,
  `python_package_root`, `image_base_name`) — never patch synced `mypy.ini` /
  `.pylintrc`.
- Temporary product-local `reusable-check-local.yml` (omit Trivy licence job) until
  [devinfra#74](https://github.com/fairagro/m4.2_middleware_devinfra/issues/74);
  delete when upstream is ready.
- Thin Helm callers → Devinfra `reusable-helm-*@main` with explicit chart inputs.
- Delete local `reusable-{code-quality,check,build,release}.yml` forks.
- Drop Wave B `load-env` CST `SKIP` workaround once Bake exists (`CST_BAKE_TARGET=api`).

## Capabilities

### New Capabilities

_None — `skip_specs: true` (tooling/CI adopt; no domain requirement deltas)._

### Modified Capabilities

_None._

## Impact

- Local and CI image builds must use `docker buildx bake api` (pins from `versions.env`).
- Feature PR / release CI identity uses explicit `image_base_name:
  fairagro-advanced-middleware`.
- Agents must not hand-edit allowlisted synced paths; caller overlays and temporary
  local check fork only.
- No HTTP API / CouchDB / Celery behaviour change.
