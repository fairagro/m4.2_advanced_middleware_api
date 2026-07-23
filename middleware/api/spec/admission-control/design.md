# Request Admission Control — Design

## Module Overview

A process-wide ASGI/Starlette middleware sits in front of FastAPI routing. It
tracks in-flight non-exempt requests with an asyncio semaphore sized from API
config. Rejected requests never reach routers or business logic.

```text
Client
  └─→ Uvicorn / ASGI
        └─→ AdmissionControlMiddleware
              ├─→ exempt path (/v3/health, /v3/readiness, /v3/liveness, …)
              │     └─→ handlers (no slot)
              ├─→ slot available → acquire → route handler → release
              └─→ at capacity → 503 + Retry-After + warning log
```

Primary module: `middleware/api/src/middleware/api/api/admission_control.py`,
wired from `fastapi_app.py`. Config fields live on the API `Config` model
(see Key Decisions).

## Key Decisions

1. **In-process concurrency limit, not per-client rate limiting**
   — The failure mode to improve is overload of a reachable process (queueing
   until TCP/proxy failures). A single semaphore of “max in-flight handlers”
   addresses that directly. Per-client or per-minute quotas are a different
   product concern and are out of scope here.

2. **Fail fast with `503` + `Retry-After`, never block in the middleware**
   — Blocking on the semaphore would still hold connections and hide pressure
   from clients and load balancers. Immediate `503` converts overload into a
   logged, retryable HTTP outcome that the api-client already treats as
   transient for ARC POSTs (`502`/`503`/`504`).

3. **Jittered `Retry-After` within a configured upper bound**
   — A fixed identical delay would synchronize clients that honour
   `Retry-After` and recreate a thundering herd. Each rejection picks an
   integer delay uniformly from `1..retry_after_seconds` (inclusive). The
   config value is therefore a maximum, not a constant. Clients that ignore
   the header still rely on their own backoff.

4. **Probe paths are exempt and do not take slots**
   — Kubernetes liveness/readiness must remain answerable under admission
   pressure. Exempting them avoids cascading restarts caused by the limiter
   itself. Exempt set: versioned system probes (`/v3/liveness`, `/v3/readiness`,
   `/v3/health` and the legacy `/v1/health`, `/v2/health` equivalents).

5. **Per-process limit, horizontal scale via replicas**
   — Matches the project’s single-worker-per-container / scale-out model. A
   shared cluster counter would add infrastructure dependency without buying
   correctness for this failure mode.

6. **Opt-in via config (disabled when unset / ≤ 0)**
   — Existing deployments must not change behaviour until operators set
   `max_concurrent_requests`. `retry_after_seconds` (jitter upper bound)
   applies only when limiting is enabled.

## Relationship to other specs

- Complements `harvest-arc-upload/` / `arc-upload/` idempotency: surplus POSTs
  become retryable `503`s rather than lost connections after accept.
- Complements `harvest-client/` transport retries: ARC POSTs already retry
  `503`; honouring `Retry-After` in the client is optional follow-up work,
  not required for this feature to ship.
- Does not replace client-side `max_concurrency`; both layers remain useful
  (client fairness vs server self-protection).
