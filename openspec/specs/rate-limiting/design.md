# Rate Limiting — Design

## Module Overview

Process-local ASGI middleware rate-limits harvest/ARC write POSTs per client before route handlers run. It is a sibling
of admission control (concurrency → `503`); this module owns per-client frequency → `429`.

```text
Client
└─→ Uvicorn / ASGI
    └─→ RateLimitingMiddleware   (when enabled; preferred outer vs admission)
        ├─→ unlisted route → next middleware / handler
        ├─→ under quota → next middleware / handler
        └─→ over quota → 429 + Retry-After + warning log
```

Primary modules: `middleware/api/src/middleware/api/api/rate_limiting.py`, wiring in `fastapi_app.py`, nested
`RateLimitingConfig` on API `Config`.

## Key Decisions

1. **Separate from admission control** — Concurrency and rate limits stay different middlewares and HTTP statuses.
2. **In-memory fixed one-minute windows** keyed by `(client_key, limit_class)` under an `asyncio.Lock`.
3. **Client key = mTLS CN, else `anonymous`** — shared bucket when certificates are optional/absent.
4. **Two limit classes** — harvest-create (`POST /v3/harvests`, default 10/min) and arc-submit (`POST /v2/arcs`,
   `POST /v3/arcs`, `POST /v3/harvests/{id}/arcs`, default 60/min). Non-positive class limit = unlimited for that class.
5. **Opt in via `rate_limiting.enabled`** — default `false`; issue defaults apply when enabled.
6. **Dedicated `retry_after_seconds`** on `RateLimitingConfig` (jittered `1..N`), independent of admission control.
7. **No Redis / slowapi** — process-local only; scale with replicas; cluster-wide limits remain an ops/Ingress concern.
8. **Starlette LIFO wiring** — rate-limiting middleware is registered after admission so it runs first on the request
   path.

## Relationship to other specs

Complements `admission-control/` (process concurrency). Applies on top of `arc-upload/` and `harvest-arc-upload/` write
paths without changing their success/idempotency contracts. Honouring `429`/`Retry-After` in `harvest-client/` is
optional follow-up work.
