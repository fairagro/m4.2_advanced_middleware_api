# Design

## Context

See proposal.md — Why. After #541 / PR #632, only `api/v1/system.py` remains under `api/v1/` (whoami / liveness /
health), registered from `fastapi_app.py`. Admission exempts `/v1/health` and `/v2/health` alongside `/v3` probes.
Shared `api_models/v1` holds response models re-exported from `api_models/__init__.py` for those routes. `system_v2`
(`GET /v2/health`) stays. Charts and docs already probe `/v3`.

## Goals / Non-Goals

**Goals:**

- Delete the `/v1` system HTTP surface and its exclusive models/tests.
- Keep admission exemptions accurate (`/v3` probes + `/v2/health` only).
- Make the breaking removal obvious in git history (`feat!:` / `BREAKING CHANGE`).

**Non-Goals:**

- Removing or deprecating `system_v2`.
- Changing `/v3` whoami / probe payloads.
- Shipping a long dual-run compatibility shim.

## Decisions

1. **Delete the whole `api/v1/` package** — Only system routes remain there; no partial stub router.
   - Alternative: leave an empty package — rejected (noise).
2. **Remove `api_models/v1` and package re-exports** — Models exist solely for those routes. Update `test_api_models` to
   stop asserting v1 `LivenessResponse` (or drop those cases).
   - Alternative: keep models “for clients” — rejected; no in-org consumers; wire models live in `v3`.
3. **Admission: drop `/v1/health` only** — Keep `/v2/health` while `system_v2` is registered.
4. **Docs** — Update `workspace.dsl` v1 router component; trim legacy `/v1/health` mentions in architecture notes that
   imply the route still exists.
5. **Breaking commit** — Single `feat!:` (or footer) covering route removal so Release major-bumps intentionally.

## Risks / Trade-offs

- **[Risk] Unknown external probe still on `/v1/health`** → Mitigation: org code search + chart/`/v3` monitor (#620)
  already checked; announce in PR/release notes; rollback = revert release.
- **[Risk] Tests still parametrize `/v1/whoami`** → Mitigation: task list retargets parametrize to `/v3` only and
  deletes dedicated `/v1/health` cases.
- **[Trade-off] `/v1/*` at capacity now counts toward admission** → Acceptable; paths return `404` after removal anyway.

## Migration Plan

1. Merge breaking change; Release notes state `/v1` system routes removed → use `/v3`.
2. Deploy; confirm chart probes (`/v3/liveness`, `/v3/readiness`) and monitoring (`/v3/health`) stay green.
3. Rollback: revert the release commit / chart pin if needed.
