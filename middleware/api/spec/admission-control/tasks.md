# Request Admission Control — Tasks

- [ ] Add API config fields for `max_concurrent_requests` (optional / ≤0 = off)
      and `retry_after_seconds` (positive int when limiting is on).
- [ ] Implement ASGI middleware with asyncio semaphore, probe-path exemption,
      `503` + `Retry-After`, warning log, and guaranteed slot release.
- [ ] Register middleware on the FastAPI app in `fastapi_app.py`.
- [ ] Unit tests: under limit → 200 path; at limit → 503 + header; probes exempt
      at capacity; disabled config → no limiting; slot released after handler error.
- [ ] Confirm api-client ARC POST retries still cover admission `503` (existing
      tests); optionally document `Retry-After` for a later client enhancement.
