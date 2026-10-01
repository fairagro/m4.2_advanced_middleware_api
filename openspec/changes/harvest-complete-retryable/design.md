# Design

## Context

Issue [#547](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/547): make harvest completion safely
retryable. Lock-ins: **Option A** (keep server re-complete + re-enqueue finalize — safe because catalog finalize is
byte-stable and skips commit/push when unchanged); **Client-Defense GET** after failed complete; **OpenSpec** deltas on
`harvest-client` (+ clarifying `harvest-manager` if needed).

## Goals / Non-Goals

**Goals:**

- ApiClient retries `POST …/complete` on the same transient policy as idempotent ARC POSTs.
- After completion failure, GET harvest; `COMPLETED` → success without requiring another successful complete response.
- Specs match Option A + GET defense.
- Preserve existing server COMPLETED replay → re-enqueue finalize.

**Non-Goals:**

- Option B (suppress finalize on COMPLETED replay).
- Idempotency-Key on complete.
- Changing cancel/fail terminal transitions.
- Fixing network ConnectError root causes.

## Decisions

1. **Keep server Option A** — `BusinessLogic.transition_harvest` already re-enqueues finalize on COMPLETED replay.
   Catalog `finalize` rebuilds byte-stable `{rdi}.json` and skips commit/push when equal (`consolidated_git` /
   arc-store). Double finalize with no new ARC commits does not rewrite catalog Git history. Reason: matches existing
   harvest-manager recovery scenario; user’s safety condition is already implemented for catalog content.

2. **Treat complete path as retryable in ApiClient** — Extend `_is_idempotent_post_path` (or equivalent) so
   `POST /v3/harvests/{id}/complete` is retryable under existing `_request_with_retries` gates. Prefer matching
   `…/complete` (and optionally PATCH-to-COMPLETED if that is the primary client path — verify which method
   `complete_harvest` uses). Reason: smallest change aligned with ARC/keyed-create retry machinery.

3. **Client-Defense GET** — On completion failure after retries (or when a non-success response leaves status
   ambiguous), call existing get-harvest; if status is `COMPLETED`, return success / harvest response; if `RUNNING`,
   surface the original error (or one more complete attempt if still within retry budget — prefer: defense runs after
   retry loop so RUNNING → fail as today unless a dedicated extra complete is simpler). Recommended MVP: after the
   complete retry loop raises/returns failure, GET once; `COMPLETED` → success; else re-raise. Reason: covers
   lost-response and older servers that might still 409; cheap defense in depth.

4. **Spec updates** — MODIFY harvest-client retry requirement: MUST retry completion; REPLACE “Do not retry harvest
   completion” with retry + GET-defense scenarios. harvest-manager: preferably no requirement change (re-complete
   already specified); optional ADDED/MODIFIED note that unchanged ARC set makes re-finalize a catalog Git no-op
   (cross-ref arc-store) if not already clear enough for operators.

5. **No new dependencies.**

## Risks / Trade-offs

| Risk                                                        | Mitigation                                          |
| ----------------------------------------------------------- | --------------------------------------------------- |
| Extra GET on every failed complete                          | Only on failure path; rare                          |
| Finalize still appends harvest catalog events on no-op push | Observability only; accepted under A                |
| PATCH vs POST complete API surface                          | Implement for the method(s) ApiClient actually uses |

## Migration Plan

1. Ship client + spec together so harvesters pick up retries.
2. No server deploy dependency for A (already compatible).
3. No data migration.

## Open Questions

_(none)_
