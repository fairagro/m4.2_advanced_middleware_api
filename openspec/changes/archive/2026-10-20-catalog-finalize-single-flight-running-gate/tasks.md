# Tasks

## 1. Harvest RUNNING gate (C)

- [x] 1.1 Add harvest-status check in `submit_arc_in_harvest` (and any shared BL helper): non-`RUNNING` →
      `ConflictError` → HTTP `409` with status in message; no ARC write / sync / per-item error — verify with unit tests
      for `COMPLETED` / `CANCELLED` / `FAILED` and a happy `RUNNING` path
- [x] 1.2 Update OpenAPI / harvests docstring for the lifecycle `409` — verify text mentions not-`RUNNING` vs
      content/identity conflicts

## 2. Finalize single-flight (A)

- [x] 2.1 Implement per-RDI lock around consolidated finalize critical section (prefer document-store claim; else
      justified alternative per design D1) used from worker `finalize_catalog` / `ArcManager.finalize_catalog` / store —
      verify unit test that two overlapping finalize calls for the same RDI do not enter the critical section
      concurrently (mock/timing or lock spy)
- [x] 2.2 Map lock wait timeout to transient retry path — verify timeout surfaces as retryable, not permanent
      `CATALOG_PUSH_FAILED` on first wait expiry
- [x] 2.3 Confirm re-complete still enqueues finalize and unchanged catalog remains Git no-op — verify existing or
      extended unit/integration coverage

## 3. Specs / docs touch-up

- [x] 3.1 Sync delta wording into implementation comments only where needed (no AGENTS essay) — verify
      `openspec validate catalog-finalize-single-flight-running-gate` passes
- [x] 3.2 Run focused pytest for harvests + finalize/catalog paths touched — verify green for affected unit suites
