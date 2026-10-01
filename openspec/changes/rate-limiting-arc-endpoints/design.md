# Design

## Context

Issue [#185](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/185) adds per-client rate limits on
harvest/ARC write POSTs. Admission control already provides process-local **concurrency** caps (`503`). Rate limiting is
a separate concern: **per-client request frequency** with `429`.

Lock-ins: in-memory limiter (no Redis/slowapi); endpoints include `POST /v3/arcs`; missing `client_id` → key
`anonymous`; issue default rates; configurable via API config file; OpenSpec capability `rate-limiting`.

## Goals / Non-Goals

**Goals:**

- Enforce configurable per-client limits on the four write POSTs listed in the proposal.
- Return `429` + `Retry-After` when a client exceeds its limit for that route class.
- Disable cleanly for development via config.
- Keep state process-local (aligned with one Uvicorn worker per container).

**Non-Goals:**

- Cluster-wide / Redis-backed counters.
- Rate-limiting all HTTP routes or probe paths.
- Changing admission-control `503` behaviour.
- Teaching `harvest-client` to honour `429`/`Retry-After` (optional follow-up).
- Re-introducing `POST /v1/arcs`.

## Decisions

1. **Separate middleware from admission control** — Rate limiting stays a sibling ASGI middleware (or thin module wired
   next to it), not an extension of the concurrency semaphore. Reason: admission-control design already separates the
   concerns; mixing counters and semantics (`503` vs `429`) would blur ops tuning.

2. **In-memory fixed window or token bucket keyed by `(client_key, limit_class)`** — Simple process-local map under an
   `asyncio.Lock` (or equivalent). Reason: no new infrastructure; matches admission-control scaling model. Exact
   algorithm (fixed window vs token bucket) is an implementation detail as long as defaults match requests-per-minute
   semantics operators expect.

3. **Client key = mTLS CN, else `anonymous`** — Reuse the same identity source as `get_client_id` (cert CN). When
   `require_client_cert` is false and no cert is present, all such callers share the `anonymous` bucket. Reason:
   fail-safe when certs are optional; avoids a silent bypass.

4. **Limit classes, not one global counter** — Two configured rates: harvest-create (`POST /v3/harvests`) default
   **10/minute**; ARC-submit (`POST /v3/arcs`, `POST /v2/arcs`, `POST /v3/harvests/{id}/arcs`) default **60/minute**.
   Reason: matches #185 table; harvest creation is rarer and more expensive to abuse.

5. **Config shape (nested under API Config)** — A dedicated nested model (e.g. `rate_limiting`) with at least:
   - `enabled: bool` (default `false` for safe roll-out in existing deployments, **or** `true` with documented defaults
     — prefer **`enabled: false` by default** so enabling is an explicit ops action; acceptance still satisfied because
     limits are configurable and documented; when enabled, issue defaults apply unless overridden)
   - `harvest_create_per_minute: int` (default `10`, `<=0` means unlimited for that class when enabled)
   - `arc_submit_per_minute: int` (default `60`, `<=0` unlimited for that class)
   - `retry_after_seconds: int` (default `60` or reuse shared jitter bound — prefer a **dedicated** field so admission
     and rate-limit retry hints can differ; jitter optional; minimum positive integer `Retry-After`) Reason:
     ConfigWrapper / nested ConfigBase pattern; `extra="forbid"` on root Config.

6. **Apply only to listed POST paths** — Path match before or after routing is fine; unlisted routes are unaffected.
   Reason: smallest security MVP surface.

7. **Ordering vs admission control** — Either order is acceptable; prefer **rate-limit before admission** so abusive
   clients get `429` without consuming concurrency slots. Reason: clearer signal and less self-DoS of the process
   budget.

8. **No new third-party rate-limit dependency** — Implement with stdlib + existing FastAPI/Starlette stack. Reason:
   Redis/slowapi rejected; keep the dependency surface small.

## Risks / Trade-offs

| Risk                                                         | Mitigation                                                     |
| ------------------------------------------------------------ | -------------------------------------------------------------- |
| Not cluster-wide — N replicas ≈ N× effective quota           | Document; Ingress/Gateway limits as future ops layer           |
| `anonymous` shared bucket can starve other cert-less clients | Acceptable in Dev; prod should keep `require_client_cert=true` |
| Clock / window edge bursts (fixed window)                    | Document; token bucket if tests show painful burstiness        |
| Default `enabled: false` vs issue “defaults apply”           | Document how to enable; defaults live in the model when on     |

## Migration Plan

1. Ship with `rate_limiting.enabled: false` (or omit nested block → defaults).
2. Operators set `enabled: true` and tune rates in YAML / env.
3. No data migration. Clients that already retry on `503` may need to treat `429` similarly (follow-up for
   `harvest-client` if desired).

## Open Questions

_(none — lock-ins closed in explore)_
