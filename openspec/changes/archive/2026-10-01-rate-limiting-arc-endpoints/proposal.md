# Proposal

## Why

Authenticated clients can flood ARC and harvest write endpoints today: there is no per-client request quota. Admission
control (`openspec/specs/admission-control/`) only caps **process-local concurrency** and returns `503` — it does not
stop one misbehaving certificate from monopolizing CouchDB writes and Celery bandwidth within that budget. Issue #185
asks for configurable per-client rate limiting with `429` + `Retry-After`.

Redis-backed libraries (e.g. slowapi) are out of scope: the product no longer uses Redis. Limits stay process-local,
matching the one-worker-per-container scaling model.

## What Changes

- Add process-local, per-client rate limiting on harvest/ARC write POSTs (token-bucket / fixed window).
- Configurable via API `Config` (YAML + env/secrets through ConfigWrapper); operators can disable for development.
- Exceeding a limit returns `429 Too Many Requests` with `Retry-After`.
- Unit tests and operator-facing config docs.
- **Not BREAKING** for clients within limits; clients that exceed limits start receiving `429` when the feature is
  enabled (default limits apply when enabled).

## Capabilities

### New Capabilities

- `rate-limiting`: Per-client HTTP rate limits on configured write endpoints; `429` + `Retry-After`; config-driven
  enablement and per-route defaults.

### Modified Capabilities

- _(none)_ — complementarity with `admission-control` is documented in the new capability’s purpose/design only; the
  concurrency contract is unchanged.

## Impact

- **Code:** New ASGI/middleware (or equivalent) beside admission control; API `Config` fields; wiring in
  `fastapi_app.py`; docs under product config / AGENTS Spec-to-Code Mapping.
- **Endpoints in scope:** `POST /v3/harvests`, `POST /v3/harvests/{harvest_id}/arcs`, `POST /v3/arcs`, `POST /v2/arcs`.
  (`POST /v1/arcs` removed — out of scope.)
- **Identity key:** mTLS certificate CN (`client_id`); missing identity uses shared key `anonymous`.
- **Ops:** Default rates from #185 (10/min harvest create, 60/min ARC POSTs); all overridable in config.
- **Out of scope:** Cluster-wide shared counters, Redis, Ingress/Gateway rate limits, Celery `task_rate_limit`, changing
  admission-control `503` semantics.
