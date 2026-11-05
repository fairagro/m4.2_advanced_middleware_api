# Tasks

## 1. Models and version source

- [ ] 1.1 Add `VersionResponse` and `version: str` on `HealthResponse` (not on `BaseStatusResponse`) in shared v3
      models; verify OpenAPI/model import still resolves
- [ ] 1.2 Centralize the existing `api` package version resolve into a reusable helper and wire FastAPI `version=`
      through it; verify unit import / fallback still yields a non-empty string under pytest

## 2. HTTP routes and admission

- [ ] 2.1 Add `GET /v3/version` (auto-`HEAD`) returning `VersionResponse` without client-cert dependency; verify
      `uv run pytest` covers `200` + body and `HEAD` with empty body
- [ ] 2.2 Include `version` on `/v3/health` for both success and failure paths; verify existing v3 system health tests
      updated for the new field (GET and HEAD status parity)
- [ ] 2.3 Add `/v3/version` to admission `_EXEMPT_PATHS` and extend admission unit parametrize; verify
      exempt-at-capacity behaviour for the path
- [ ] 2.4 Update `openspec/specs/admission-control/design.md` probe list to mention `/v3/version`; verify text matches
      the delta requirement

## 3. Docs mapping

- [ ] 3.1 Add Spec-to-Code Mapping row for `api-version` in `AGENTS.md` pointing at v3 system routes + models; verify
      the row is accurate vs implementation paths
