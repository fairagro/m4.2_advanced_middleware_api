# Design

## Context

See `proposal.md` for motivation. Today `__version__` is resolved once in `fastapi_app.py` via
`importlib.metadata.version("api")` (with pyproject / `0.0.0` fallbacks) and passed only to FastAPI `version=`. System
routes live in `api/v3/system.py`; health models share `BaseStatusResponse` (`status`, `services`). Admission exempts a
fixed path set in `admission_control.py`. FastAPI registers `HEAD` automatically for `@router.get` routes unless
disabled.

## Goals / Non-Goals

**Goals:**

- Single shared resolve for the PEP 440 string used by OpenAPI, `/v3/version`, and `/v3/health`.
- Probe-class trust and admission behaviour for `/v3/version` (GET + HEAD).
- Additive `version` only on `HealthResponse`.

**Non-Goals:**

- `api_client` helper, local-offline parity, version on liveness/readiness, rate-limit changes (writes-only today).

## Decisions

1. **Shared version helper** — Extract the existing resolve into a small module-level function (or keep exporting
   `__version__` from `fastapi_app` / a tiny `package_version` helper) and reuse it in system routes. Reason: one
   fallback chain; avoid duplicating pyproject reads. Alternative: call `importlib.metadata` in the route only —
   rejected because OpenAPI and HTTP could diverge in edge environments.

2. **`version` only on `HealthResponse`** — Do not put it on `BaseStatusResponse`. Reason: lock-in keeps k8s
   liveness/readiness payloads minimal; monitoring that wants version uses `/v3/version` or health.

3. **`VersionResponse` model** — Dedicated `{version: str}` model for `/v3/version`. Reason: clear OpenAPI schema;
   avoids overloading health models.

4. **HEAD via FastAPI GET registration** — Keep `@router.get` so Starlette/FastAPI adds HEAD with the same status and no
   body. Reason: matches HTTP semantics and UptimeRobot-style HEAD probes without a second handler. Alternative:
   explicit `@router.api_route(..., methods=["GET","HEAD"])` — only if auto-HEAD is disabled project-wide (it is not).

5. **Admission exempt `/v3/version`** — Add to `_EXEMPT_PATHS` and update admission-control design/spec. Reason: version
   must remain readable under overload like other probes.

6. **No cert dependency** — Version/health routes continue to use only `get_accept_type` (+ health service for health),
   never `get_client_id`. Reason: same trust model as existing probes.

## Risks / Trade-offs

- **[Risk] Exact JSON assertions in health unit tests break** → Update tests to expect `version`; pin via mock of the
  shared resolve where useful.
- **[Risk] Package not installed in some test contexts yields `0.0.0`** → Accept existing fallback; assert non-empty
  string / mocked value rather than a release tag in unit tests.
- **[Trade-off] HEAD not listed separately in OpenAPI** → Acceptable; HTTP clients still get HEAD behaviour from GET
  routes.

## Migration Plan

- Deploy anytime: additive field + new path. No config migration.
- Rollback: revert release; clients ignoring unknown fields keep working; clients calling `/v3/version` get `404`.
