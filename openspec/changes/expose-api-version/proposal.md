# Proposal

## Why

Operators and clients need a stable HTTP contract for the PEP 440 package version stamped into the middleware-api image
at release. Today that value appears only as FastAPI `info.version` via `/openapi.json`, which is not a reliable client
or monitoring contract. Probe endpoints do not expose version; health alone is a poor sole channel because it may return
`503` when dependencies fail.

## What Changes

- Add `GET` / `HEAD` `/v3/version` returning the installed `api` package PEP 440 version (`200`, no dependency checks,
  no client certificate).
- Extend `GET` / `HEAD` `/v3/health` with an additive `version` field (same string), present on both `200` and `503`
  responses. Liveness and readiness stay unchanged (no `version`).
- Exempt `/v3/version` from process-local admission control (same class as other probes).
- Document the contract in a new `api-version` capability and update `admission-control` requirements.

Non-goals: `api_client` helper, local-offline `/v3/version`, version on liveness/readiness, waiting for v4 (#556).

## Capabilities

### New Capabilities

- `api-version`: HTTP contract for reading the installed API PEP 440 version via `/v3/version` and the additive
  `version` field on `/v3/health`.

### Modified Capabilities

- `admission-control`: Exempt `/v3/version` (GET and HEAD) alongside existing probe paths.

## Impact

- Code: `middleware/api/.../api/v3/system.py`, shared v3 models (`HealthResponse`, new `VersionResponse`), admission
  exempt list, unit tests for system/admission routes.
- Specs: new `openspec/specs/api-version/`; delta `openspec/specs/admission-control/`.
- AGENTS.md Spec-to-Code Mapping for `api-version`.
- No breaking wire change (additive JSON field; new path).
