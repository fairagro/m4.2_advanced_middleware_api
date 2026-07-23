# Request Admission Control

Cap concurrent in-flight HTTP request handling inside the API process. When
the process is at capacity but still reachable, reject surplus requests with
`503 Service Unavailable` and a `Retry-After` header so clients see an HTTP
signal (and the API emits logs) instead of a transport-level `ConnectError`.

## Requirements

- [ ] Enforce a configurable maximum number of concurrent in-flight API
      requests per API process.
- [ ] Accept a request into the limit before running the route handler; release
      the slot when the response completes (including errors).
- [ ] When the limit is already reached, respond with `503 Service Unavailable`
      without running the route handler.
- [ ] Include a `Retry-After` response header on every admission-rejected
      `503`, with a positive delay in seconds chosen uniformly at random from
      `1` through a configured inclusive upper bound (to spread client retries).
- [ ] Log every admission rejection at warning level, including the configured
      limit and the current in-flight count.
- [ ] Exempt liveness, readiness, and health probe paths from the limit so
      orchestration probes are not starved under load.
- [ ] Apply the limit to all other HTTP methods and API versions served by the
      process (including ARC upload POSTs).
- [ ] Keep admission control disabled when the configured maximum is unset or
      non-positive, so existing deployments without the setting behave as today.

## Edge Cases

Configured maximum is unset or ≤ 0 → no admission limiting; every reachable
request is handled as without this feature.

In-flight count equals the maximum → next non-exempt request receives `503`
with `Retry-After`; no business logic runs for that request.

Exempt probe path while at capacity → probe is handled normally; it does not
consume an admission slot and does not receive `503` from this feature.

Handler raises after acquiring a slot → slot is still released; subsequent
requests may be admitted.

Multiple API replicas → each process enforces its own limit independently;
there is no cluster-wide shared counter.

Client retries a `503` on an idempotent ARC POST (see `harvest-arc-upload/` /
`arc-upload/` and `harvest-client/`) → retry is safe for identical bodies;
admission control does not change that contract.
