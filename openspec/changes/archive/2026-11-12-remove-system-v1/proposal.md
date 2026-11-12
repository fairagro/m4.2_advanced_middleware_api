# Proposal

## Why

Deprecated `system_v1` routes (`GET /v1/whoami`, `/v1/liveness`, `/v1/health`) remain registered only for compatibility
after #541 / PR #632. `/v3` already covers the same capabilities; charts and in-repo clients use `/v3`. Leaving `/v1`
forever keeps a dual surface and admission/docs debt. Caller check (#633) found no remaining org consumers.

## What Changes

- **BREAKING**: Remove `system_v1` router registration and `middleware/api/.../api/v1/` system endpoints (`/v1/whoami`,
  `/v1/liveness`, `/v1/health`).
- Remove v1-only response models and shared re-exports that exist solely for those routes; drop or retarget tests that
  parametrize `/v1` system paths.
- Drop legacy `/v1/health` from admission-control exempt probe paths (`/v2/health` stays while `system_v2` remains).
- Update architecture docs (`workspace.dsl` and related notes) so `/v1` system routes are gone.

Non-goals: remove `system_v2` / `/v2/health`; change `/v3` probe contracts; migrate external operators beyond announcing
the breaking release.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `admission-control`: Exempt probe list no longer includes `/v1/health` (only `/v3/*` probes plus `/v2/health` while
  still registered).

## Impact

- **BREAKING API**: Clients calling `/v1/whoami`, `/v1/liveness`, or `/v1/health` receive `404` after deploy. Prefer
  `/v3/whoami`, `/v3/liveness`, `/v3/readiness`, `/v3/health`.
- Code: `fastapi_app.py`, delete `api/v1/`, `admission_control.py`, shared `api_models/v1` + package re-exports, unit
  tests (`test_middleware_api`, `test_whoami`, `test_admission_control`, `test_api_models`), `workspace.dsl`.
- Specs: delta `openspec/specs/admission-control/`.
- Commit: Conventional Commits `feat!:` (or `BREAKING CHANGE:` footer) so Release bumps major when appropriate.
