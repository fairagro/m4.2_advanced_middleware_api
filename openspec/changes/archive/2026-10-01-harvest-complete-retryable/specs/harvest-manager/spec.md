# Harvest Manager Delta

## MODIFIED Requirements

### Requirement: Finalize ArcStore catalog on harvest completion

When a harvest transitions to `COMPLETED` and a `consolidated_store` is configured, the system SHALL enqueue an
asynchronous worker task that calls catalog `finalize(rdi=…)` on that consolidated store for the harvest’s RDI. When
`consolidated_store` is absent, the system MUST NOT enqueue catalog finalize. Harvest status transition to `COMPLETED`
MUST NOT wait for per-ARC Git sync or catalog finalize to finish. When finalize runs, the system MUST record distinct
catalog events for publish success and failure so operators can distinguish “harvest complete” from “RDI catalog
flushed”. When `consolidated_store` is configured, the system MUST enqueue finalize on harvest `COMPLETED` even when
statistics show no new or updated ARCs (bootstrap and retry after a failed finalize). Byte-stable comparison still
governs whether a Git push occurs. Worker task payloads MAY include `harvest_id` for correlation only; catalog
membership is always “all current ARCs for the RDI”. There is no requirement that all per-ARC syncs complete before
finalize runs. Re-requesting `COMPLETED` on an already-`COMPLETED` harvest MUST re-enqueue finalize when
`consolidated_store` is configured; when the ARC set is unchanged, catalog finalize MUST NOT create a new catalog Git
commit (identical catalog bytes → skip commit/push), so a second finalize after a lost HTTP response is safe for catalog
content.

#### Scenario: Complete harvest enqueues catalog finalize

- **GIVEN** a running harvest for RDI `edal` with `consolidated_store` configured and at least one new or updated ARC
- **WHEN** the harvest is completed
- **THEN** the harvest status becomes `COMPLETED` and a finalize task for `edal` is enqueued

#### Scenario: Unchanged harvest still enqueues catalog finalize

- **GIVEN** a consolidating harvest whose statistics show only unchanged ARCs and `consolidated_store` is configured
- **WHEN** the harvest is completed
- **THEN** a finalize task for that RDI is still enqueued
- **AND** the worker MAY skip commit/push when catalog bytes already match the remote

#### Scenario: Finalize no-op on per-ARC backends

- **GIVEN** only `arc_store` is configured (no `consolidated_store`)
- **WHEN** a harvest completes
- **THEN** no catalog finalize task is enqueued
- **AND** the harvest transition still succeeds

#### Scenario: Catalog push failure is observable

- **GIVEN** finalize fails permanently after harvest `COMPLETED` with `consolidated_store` configured
- **WHEN** the worker records the outcome
- **THEN** a catalog-failure event is stored and the harvest remains `COMPLETED` (retry of finalize is allowed without
  re-opening the harvest)

#### Scenario: Transient catalog push does not record failure before retry

- **GIVEN** finalize raises a retryable store error after harvest `COMPLETED` and Celery will still retry
- **WHEN** the worker re-raises for Celery retry
- **THEN** no `CATALOG_PUSH_FAILED` event is appended (matching per-ARC `GIT_PUSH_*` handling); a later successful
  attempt MAY record only `CATALOG_PUSH_SUCCESS`

#### Scenario: Exhausted transient catalog push records failure once

- **GIVEN** finalize raises a retryable store error after harvest `COMPLETED` on the final Celery attempt (`retries`
  exhausted)
- **WHEN** the worker re-raises `TransientError` (task ends in `FAILURE`)
- **THEN** exactly one `CATALOG_PUSH_FAILED` event is appended (redacted message)
- **AND** the harvest remains `COMPLETED`

#### Scenario: Re-complete after dispatch failure re-enqueues finalize

- **GIVEN** a harvest already in `COMPLETED` whose Celery finalize dispatch failed and `consolidated_store` is
  configured
- **WHEN** the client requests `COMPLETED` again for that harvest
- **THEN** the harvest document is not rewritten
- **AND** a finalize task for that RDI is enqueued again

#### Scenario: Unchanged ARC set makes second finalize a catalog Git no-op

- **GIVEN** a harvest already `COMPLETED` and catalog finalize previously published catalog bytes for its RDI
- **AND** no ARC content for that RDI has changed
- **WHEN** finalize runs again after a re-complete enqueue
- **THEN** catalog Git commit/push is skipped because the rebuilt catalog bytes match the tip
