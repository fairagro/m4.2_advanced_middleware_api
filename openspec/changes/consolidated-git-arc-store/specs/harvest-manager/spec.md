# Harvest Manager — Delta

## ADDED Requirements

### Requirement: Finalize ArcStore catalog on harvest completion

When a harvest transitions to `COMPLETED`, the system SHALL request ArcStore
`finalize(rdi=…)` for that harvest’s RDI (via an asynchronous worker task).
Harvest status transition to `COMPLETED` MUST NOT wait for the Git push to
finish. The system MUST record distinct catalog events for publish success and
failure so operators can distinguish “harvest complete” from “RDI catalog
flushed”. The system MAY skip enqueueing finalize when harvest statistics show
no new or updated ARCs; when finalize runs, byte-stable comparison still
governs whether a Git push occurs. Worker task payloads MAY include
`harvest_id` for correlation only; catalog membership is always “all current
ARCs for the RDI”.

#### Scenario: Complete harvest enqueues catalog finalize

- **GIVEN** a running harvest for RDI `edal` with the consolidated backend
  configured and at least one new or updated ARC
- **WHEN** the harvest is completed
- **THEN** the harvest status becomes `COMPLETED` and a finalize task for
  `edal` is enqueued

#### Scenario: Finalize no-op on per-ARC backends

- **GIVEN** `git_repo` is configured
- **WHEN** a harvest completes
- **THEN** finalize is still invoked and succeeds as a no-op without failing
  the harvest transition

#### Scenario: Catalog push failure is observable

- **GIVEN** finalize fails permanently after harvest `COMPLETED`
- **WHEN** the worker records the outcome
- **THEN** a catalog-failure event is stored and the harvest remains
  `COMPLETED` (retry of finalize is allowed without re-opening the harvest)

#### Scenario: Transient catalog push does not record failure before retry

- **GIVEN** finalize raises a retryable store error after harvest `COMPLETED`
- **WHEN** the worker re-raises for Celery retry
- **THEN** no `CATALOG_PUSH_FAILED` event is appended (matching per-ARC
  `GIT_PUSH_*` handling); a later successful attempt MAY record only
  `CATALOG_PUSH_SUCCESS`
