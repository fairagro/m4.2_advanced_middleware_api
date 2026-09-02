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

The system SHALL transition a harvest through an explicit operation to one of `COMPLETED`, `CANCELLED`, or `FAILED`.
Only `RUNNING` harvests MAY make a terminal transition; otherwise it MUST raise `ConflictError` with the current status.

#### Scenario: Transition an already terminal harvest

- **GIVEN** a harvest not in `RUNNING`
- **WHEN** a terminal transition is requested
- **THEN** `ConflictError` identifies its current status

#### Scenario: Submit duplicate ARC content during a harvest

- **GIVEN** an ARC identifier submitted twice in one harvest
- **WHEN** its content is identical
- **THEN** ingestion succeeds idempotently as specified in `arc-manager/` and `harvest-arc-upload/`

#### Scenario: Submit conflicting ARC content during a harvest

- **GIVEN** an ARC identifier submitted once in one harvest
- **WHEN** different content is submitted
- **THEN** ingest rejects it with `DuplicateArcError` as specified in `arc-manager/`
