# Proposal

## Why

Harvester and SQL-to-ARC can produce RO-Crate that later fails DataHUB’s `arc-export` CI check. Clients need the same
gate locally and in their CI without standing up Middleware API, Celery, CouchDB, or GitLab. Shared tooling for that
check belongs in this repo as a published library.

## What Changes

- Add workspace package `middleware/arc_validation/` published as `fairagro-middleware-arc-validation` (hatch-vcs).
- Public API: write ARC scaffold via ARCtrl, run `arc-export` in Docker, validate RO-Crate end-to-end, return
  `ArcExportResult` (ok, exit code, stdout/stderr, cause excerpt).
- CLI entry point `fairagro-arc-validate` for path-based checks (exit 0/non-zero).
- Defaults match DataHUB CI (`ghcr.io/nfdi4plants/arc-export:main`, formats `rocrate-metadata-lfs`, `isa-json`,
  `summary-markdown`) with documented image digest override.
- Unit tests with mocked Docker; optional marked live Docker test.
- Wire package into uv workspace + PyPI release publishing; README + AGENTS Spec-to-Code mapping.
- OpenSpec capability `arc-export-validation`; extend `ci-cd` PyPI naming/publish requirements for the third package.

Non-goals: API upload/Celery/Git/CouchDB tests; owning client RDI fixtures; replacing DataHUB CI; client-repo
integration PRs (follow-ups after PyPI ships).

## Capabilities

### New Capabilities

- `arc-export-validation`: Contract for the shared ARCtrl write → Docker `arc-export` validation pipeline and result
  type used by harvester / SQL-to-ARC (and this repo’s tests).

### Modified Capabilities

- `ci-cd`: PyPI publish MUST include `fairagro-middleware-arc-validation` alongside shared and api-client.

## Impact

- New package under `middleware/arc_validation/` (depends on `arctrl`; not on FastAPI/Celery/CouchDB).
- Root `pyproject.toml` workspace member; quality/MYPYPATH overlays may need the new src/tests roots.
- Release/publish workflow / Devinfra reusable inputs for an extra wheel.
- Channel: `build/issue-317-arc-export-validation`.
