# Design

## Context

See proposal.md. Consumers need ARCs on disk via `ApiClient` without the full API stack. A module inside `api` forces
Celery/CouchDB/Git deps into consumer testenvs — wrong for CI.

## Goals / Non-Goals

**Goals:**

- Publishable light package installable next to `fairagro-middleware-api-client`.
- Enough HTTP for `harvest_arcs`; filesystem write before submit success.
- Same version stamp as other Middleware PyPI packages.

**Non-Goals:**

- Depending on package `api`.
- Subclassing production `middleware.api.arc_store.ArcStore` (optional later adapter).
- Production-parity 409 semantics; catalog finalize; consumer-repo adopt in this change.

## Decisions

### 1. Separate workspace package, not an `api` submodule

**Choice:** `middleware/api_local_offline/` → PyPI `fairagro-middleware-api-local-offline`, import
`middleware.api_local_offline`.

**Why:** Consumer test suites stay light. Compose can `pip install` into `python:slim` or `uvx` the CLI.

### 2. Dependencies

**Choice:** `fairagro-middleware-shared`, `arctrl`, `fastapi`, `uvicorn` (+ transitive pydantic/yaml). Inline the small
`calculate_arc_id` helper (same strip+sha256 contract as `middleware.api.utils`) to avoid an `api` dependency.

### 3. Filesystem writer without api.ArcStore ABC

**Choice:** Stand-alone writer class with `create_or_update` / `check_health` / no-op finalize semantics. Spec language
under `arc-store` describes behaviour, not inheritance.

### 4. Consumer usage

```text
# CI / venv
uv add fairagro-middleware-api-local-offline fairagro-middleware-api-client

# Process
middleware-api-local-offline --config local_offline.yaml --port 8000

# Or ASGI in pytest
app = create_local_offline_app(LocalOfflineConfig(output_root=tmp_path))
```

### 5. Publish

**Choice:** Add package to `.github/workflows/publish-pypi.yml` matrix; extend ci-cd spec from three packages to four.
Same hatch-vcs tag scheme as siblings.

### 6. Remove prior in-api prototype

**Choice:** Delete `middleware.api.local_offline` and the `local-offline` branch of `middleware.api.main` if present;
keep only the new package.

## Risks / Trade-offs

- [Duplicated calculate_arc_id] → Keep comment pointing at api.utils; shared extract later if needed.
- [api.ArcStore not shared] → Acceptable; stand-in is not the production sync path.

## Open Questions

None blocking apply.
