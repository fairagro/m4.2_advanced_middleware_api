# Tasks

## 1. Package and config

- [x] 1.1 Add workspace package `fairagro-middleware-api-local-offline` with light deps (shared, arctrl, fastapi,
      uvicorn) and verify it installs without package `api`
- [x] 1.2 Add `LocalOfflineConfig` that rejects production API keys and verify unit tests

## 2. Filesystem persistence and HTTP

- [x] 2.1 Implement filesystem ARC writer + thin `/v3` harvest HTTP; verify unit/smoke tests including
      `ApiClient.harvest_arcs` and disk-before-success
- [x] 2.2 Map write failures to HTTP 500; verify unit test

## 3. Publish and DX

- [x] 3.1 Add package to uv workspace, `publish-pypi.yml` matrix, MYPYPATH/pylint overlays, and package README; verify
      `uv build --package fairagro-middleware-api-local-offline`
- [x] 3.2 Remove any in-`api` prototype (`local_offline` module / main branch); verify production `api` entry unchanged
- [x] 3.3 Update AGENTS Spec-to-Code Mapping and OpenSpec deltas (`local-offline-profile`, `arc-store`, `ci-cd`); verify
      `openspec validate --strict`

## 4. Integration check

- [x] 4.1 Run focused pytest + ruff on the new package; verify green
