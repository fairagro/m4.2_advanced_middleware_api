# Request Admission Control — Design

## Module Overview

A process-wide ASGI/Starlette middleware precedes FastAPI routing. It tracks non-exempt in-flight requests with an
in-memory counter guarded by `asyncio.Lock`; rejected requests never reach routers or business logic.

```text
Client
└─→ Uvicorn / ASGI
    └─→ AdmissionControlMiddleware
        ├─→ exempt probe → handler (no slot)
        ├─→ slot available → acquire → handler → release
        └─→ at capacity → 503 + Retry-After + warning log
```

Primary modules are `middleware/api/src/middleware/api/api/admission_control.py` and `fastapi_app.py`; API `Config` owns
the configuration fields.

## Key Decisions

1. **Process concurrency, not client rate limits** — A semaphore of active handlers directly addresses a reachable
   process under load. Per-client and per-minute quotas are separate concerns.
2. **Fail fast** — The middleware never waits on a full semaphore; immediate `503` exposes pressure to clients and load
   balancers. The API client already treats `502`/`503`/`504` on ARC POSTs as transient.
3. **Jitter `Retry-After`** — Every rejected request uniformly selects an integer in `1..retry_after_seconds`,
   preventing synchronized retry herds.
4. **Probe paths do not take slots** — `/v3/liveness`, `/v3/readiness`, `/v3/health`, and legacy `/v1/health` and
   `/v2/health` remain reachable under load.
5. **Scale through replicas** — The per-process design matches the one-worker-per-container model; a shared counter
   would add infrastructure without improving this failure mode.
6. **Opt in through configuration** — `max_concurrent_requests` unset or non-positive disables admission control;
   `retry_after_seconds` applies only when enabled.

## Relationship to other specs

This complements `arc-upload/` and `harvest-arc-upload/`: surplus POSTs become retryable `503`s rather than lost
connections. It also complements `harvest-client/` retries; honoring `Retry-After` in that client is optional follow-up
work, and client-side `max_concurrency` remains useful for fairness.
