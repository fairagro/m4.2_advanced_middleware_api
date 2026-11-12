# Tasks

## 1. Drop `/v1` system routes and models

- [ ] 1.1 Unregister `system_v1` in `fastapi_app.py` and delete `middleware/api/.../api/v1/` (verify: package gone; app
      import has no `system_v1`).
- [ ] 1.2 Delete `middleware/shared/.../api_models/v1/` and remove v1 re-exports from `api_models/__init__.py` (verify:
      no remaining imports of `api_models.v1`).
- [ ] 1.3 Retarget or delete unit tests that hit `/v1/whoami`, `/v1/liveness`, `/v1/health`, and v1-only model cases
      (`test_middleware_api`, `test_whoami`, `test_api_models`) (verify:
      `uv run pytest middleware/api/tests/unit/test_middleware_api.py middleware/api/tests/unit/test_whoami.py middleware/shared/tests/unit/test_api_models.py -v`).

## 2. Admission control + docs

- [ ] 2.1 Remove `/v1/health` from `admission_control` exempt paths and update `test_admission_control` (verify:
      `uv run pytest middleware/api/tests/unit/test_admission_control.py -v`; `/v1/health` not treated as exempt).
- [ ] 2.2 Update `docs/architecture/workspace.dsl` (and any note that still implies live `/v1` system routes) (verify:
      no remaining “GET /v1/whoami|liveness|health” as current API surface).

## 3. Integration check

- [ ] 3.1 Run focused quality on touched Python: format/check + the pytest suites above (verify:
      `uv run ruff format --config ruff.toml` / `uv run ruff check --config ruff.toml` on touched paths; tests green).
