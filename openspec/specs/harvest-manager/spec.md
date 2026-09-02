# Harvest Management

## Purpose

Harvest management tracks creation, progress, and finalization of harvest runs while enforcing client ownership. It
delegates persistence to the document store and derives final statistics from ARC documents.

## Requirements

### Requirement: Create and retrieve harvest runs

The system SHALL create a CouchDB harvest document with its `harvest_id`, `client_id`, and `rdi`. It MUST accept
optional `expected_datasets` for progress tracking and retrieve a run by `harvest_id`.

#### Scenario: Create without an expected dataset count

- **GIVEN** a create request without `expected_datasets`
- **WHEN** the harvest is created
- **THEN** it has no progress denominator and progress reports raw counts only

#### Scenario: Retrieve an unknown harvest

- **GIVEN** an unknown `harvest_id`
- **WHEN** it is retrieved
- **THEN** `ResourceNotFoundError` is raised with the ID in the message

### Requirement: Enforce harvest ownership

The system SHALL validate that the requesting client matches the stored `client_id` and MUST raise `AccessDeniedError`
on mismatch without revealing the stored client ID.

#### Scenario: Deny another client's harvest

- **GIVEN** an existing harvest owned by a different client
- **WHEN** that client accesses it
- **THEN** `AccessDeniedError` is raised without disclosing the owner

### Requirement: Derive and persist terminal statistics

When finalizing, the system SHALL derive statistics through `DocumentStore.get_harvest_statistics` for ARC
documents with matching `metadata.last_harvest_id`. It MUST classify them as new, updated, or unchanged with
`first_harvest_id` and `last_changed_harvest_id`, mark the harvest complete, and record the resulting snapshot.
Statistics MUST be complete for harvests whose ARC count exceeds the document store's default query page size.

#### Scenario: Finalize before all uploads arrive

- **GIVEN** a harvest whose expected uploads are incomplete
- **WHEN** it is finalized
- **THEN** it completes with the statistics currently available and does not enforce `expected_datasets`

#### Scenario: Finalize a large harvest

- **GIVEN** a harvest with more ARC submissions than `default_query_limit`
- **WHEN** the harvest transitions to a terminal status
- **THEN** persisted `statistics.arcs_submitted` equals the number of ARC documents last seen in that harvest
- **AND** the new/updated/unchanged breakdown matches the full set, not only the first query page

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

#### Scenario: Submit duplicate ARC content during a harvest

- **GIVEN** an ARC identifier submitted twice in one harvest
- **WHEN** its content is identical
- **THEN** ingestion succeeds idempotently as specified in `arc-manager/` and `harvest-arc-upload/`

#### Scenario: Submit conflicting ARC content during a harvest

- **GIVEN** an ARC identifier submitted once in one harvest
- **WHEN** different content is submitted
- **THEN** ingest rejects it with `DuplicateArcError` as specified in `arc-manager/`

### Requirement: Finalize ArcStore catalog on harvest completion

When a harvest transitions to `COMPLETED`, the system SHALL request ArcStore
`finalize(rdi=…)` for that harvest’s RDI (via an asynchronous worker task).
Harvest status transition to `COMPLETED` MUST NOT wait for the Git push to
finish. The system MUST record distinct catalog events for publish success and
failure so operators can distinguish “harvest complete” from “RDI catalog
flushed”. The system MUST enqueue finalize on harvest ``COMPLETED`` even when
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

### Requirement: Surface partial-push skips on catalog success events

When the worker records a harvest catalog success event (`CATALOG_PUSH_SUCCESS`)
after consolidated catalog finalize, and the finalize outcome reports one or
more skipped ARCs, the event message MUST include the number of Datasets
included, the number of skips, and a bounded list of skipped `arc_id` values so
operators can see omissions without reading worker logs. When there are no
skips, the success message MAY omit skip details. Permanent finalize failures
continue to record `CATALOG_PUSH_FAILED` as today. The system MUST NOT add a
new catalog event type solely for partial success in this change.

#### Scenario: Success event mentions skipped ARCs

- **GIVEN** a harvest-scoped catalog finalize that published (or left unchanged)
  a catalog while skipping one or more ARCs
- **WHEN** the worker appends `CATALOG_PUSH_SUCCESS` to that harvest
- **THEN** the event message includes the skip count and at least one skipped
  `arc_id`

#### Scenario: Success with no skips stays concise

- **GIVEN** a harvest-scoped catalog finalize with zero skipped ARCs
- **WHEN** the worker appends `CATALOG_PUSH_SUCCESS`
- **THEN** the event type remains `CATALOG_PUSH_SUCCESS`
- **AND** the message still indicates publish or unchanged outcome for the RDI
