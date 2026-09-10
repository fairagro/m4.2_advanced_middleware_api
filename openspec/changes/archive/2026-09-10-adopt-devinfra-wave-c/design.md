# Adopt Devinfra Wave C — Design

## Context

See `proposal.md`. Pilot lock-ins from harvester Wave C apply unless this repo
documents an exception ([#368 comment](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/368)).

**Golden rule:** (1) Devinfra generic enough for verbatim use → (2) `.global` +
product-local split → (3) only then documented local drift. Never silently re-patch
allowlisted blobs ([devinfra#57](https://github.com/fairagro/m4.2_middleware_devinfra/issues/57)).

## Goals / Non-Goals

**Goals:** Callers → Devinfra reusables; Bake product-app layout; thin Helm; remove
local reusable forks; drop CST SKIP once Bake works.

**Non-Goals:** Waiting for Devinfra [#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)
sync automation; [#40](https://github.com/fairagro/m4.2_middleware_devinfra/issues/40) markdown in CQ;
implementing [#74](https://github.com/fairagro/m4.2_middleware_devinfra/issues/74) / merging [#72](https://github.com/fairagro/m4.2_middleware_devinfra/pull/72)
inside this product PR; secondary onefile binary ([#71](https://github.com/fairagro/m4.2_middleware_devinfra/issues/71)).

## Decisions

### D1: Bake before caller switch

Land `docker-bake.hcl` + thin `Dockerfile.api`, smoke `docker buildx bake api`, then
point build/check/release at Devinfra.

### D2: Code-quality pin until #72 on main

Pin `reusable-code-quality.yml@a061d6fb85afc8dfd54083ff58bf788744dcdca8` (PR #72 tip)
with:

- `python_package_root: middleware`
- `mypy_path: stubs:middleware/api/src:middleware/api_client/src:middleware/shared/src:middleware/api/tests/unit:middleware/api_client/tests/unit:middleware/shared/tests`
- `pylint_source_roots: middleware/api/src,middleware/api/tests/unit,middleware/api_client/tests/unit,middleware/shared/tests`

Switch pin to `@main` after #72 merges. Never encode paths in synced fragments.

### D3: Temporary local check caller (not synced-tree edit)

Until #74, keep `.github/workflows/reusable-check-local.yml` (omit licence-check),
documented TEMP. Callers use it; delete when Devinfra check is non-failing on Alpine
GPL noise.

### D4: Keep feature-PR detect-changes

Product exception vs harvester: retain `detect-changes` + `skip` inputs (Devinfra
reusables still support `skip`).

### D5: Explicit Bake / image identity

Bake target `api` matches `components: '["api"]'`. `image_base_name:
fairagro-advanced-middleware`. `UV_BUILD_PACKAGES=fairagro-middleware-shared api`,
`BINARY_NAME=middleware-api`, `PYINSTALLER_IMPORT=middleware.api`, plus current
hidden-import / copy-metadata / collect-data flags via `EXTRA_PYINSTALLER_ARGS`.

### D6: Helm thin callers

`chart_dir: helmchart/fairagro-advanced-middleware-api-chart`, chart name matching
today’s `CHART_NAME`. Pass other required Devinfra helm inputs explicitly.

## Risks / Trade-offs

| Risk | Mitigation |
| ---- | ---------- |
| #72 not on main | SHA pin; flip to `@main` after merge |
| Trivy licence fails CI | Local check until #74 |
| PyInstaller flag drift | Port current Dockerfile.api flags into Bake args; smoke bake + CST |
| Synced base drift | Refresh `Dockerfile.product-app.base` from Devinfra only if Wave B pin differs — verbatim sync, no local edits |

## Open Questions

_None blocking — follow harvester pilot + #368 lock-ins._
