# Harvest Manager — Delta

## ADDED Requirements

### Requirement: Finalize ArcStore catalog on harvest completion

When a harvest transitions to `COMPLETED`, the system SHALL request ArcStore
`finalize(rdi=…)` for that harvest’s RDI (via an asynchronous worker task).
Harvest status transition to `COMPLETED` MUST NOT wait for the Git push to
finish. The system MUST record distinct catalog events for publish success and
failure so operators can distinguish “harvest complete” from “RDI catalog
flushed”. The system MUST enqueue finalize on harvest `COMPLETED` even when
statistics show no new or updated ARCs (bootstrap after switching backends and
retry after a failed finalize). When finalize runs, byte-stable comparison
still governs whether a Git push occurs. Worker task payloads MAY include
`harvest_id` for correlation only; catalog membership is always “all current
ARCs for the RDI”.

#### Scenario: Complete harvest enqueues catalog finalize

- **GIVEN** a running harvest for RDI `edal` with the consolidated backend
  configured and at least one new or updated ARC
- **WHEN** the harvest is completed
- **THEN** the harvest status becomes `COMPLETED` and a finalize task for
  `edal` is enqueued

#### Scenario: Unchanged harvest still enqueues catalog finalize

- **GIVEN** a consolidating harvest whose statistics show only unchanged ARCs
- **WHEN** the harvest is completed
- **THEN** a finalize task for that RDI is still enqueued
- **AND** the worker MAY skip commit/push when catalog bytes already match the remote

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

#### Scenario: Re-complete after dispatch failure re-enqueues finalize

- **GIVEN** a harvest already in `COMPLETED` (status persisted) whose Celery
  finalize dispatch failed
- **WHEN** the client requests `COMPLETED` again for that harvest
- **THEN** the harvest document is not rewritten
- **AND** a finalize task for that RDI is enqueued again

## MODIFIED Requirements

### Requirement: Guard terminal state transitions

The system SHALL transition a harvest through an explicit operation to one of
`COMPLETED`, `CANCELLED`, or `FAILED`. Only `RUNNING` harvests MAY transition to
a **different** terminal status. Requesting `COMPLETED` when the harvest is
already `COMPLETED` MUST succeed as an idempotent no-op (no document rewrite)
so catalog finalize can be re-enqueued. Any other non-`RUNNING` current status
MUST raise `ConflictError` with the current status.

#### Scenario: Transition an already terminal harvest to another status

- **GIVEN** a harvest not in `RUNNING` (e.g. `COMPLETED`, `CANCELLED`, `FAILED`)
- **WHEN** a terminal transition to a different status is requested
- **THEN** `ConflictError` identifies its current status

#### Scenario: Re-request COMPLETED on an already COMPLETED harvest

- **GIVEN** a harvest already in `COMPLETED`
- **WHEN** `COMPLETED` is requested again
- **THEN** the operation succeeds without rewriting the harvest document
