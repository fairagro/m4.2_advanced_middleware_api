# ARC Ingestion Pipeline

## Purpose

The shared ARC ingestion pipeline accepts a structurally validated RO-Crate, persists it quickly in the document store,
and schedules asynchronous Git sync. It serves both standalone and harvest-scoped callers and is independent of HTTP;
Git persistence is specified in `arc-store/`.

## Requirements

### Requirement: Validate the RO-Crate wire payload

The system SHALL accept only a `RoCratePayload`, or a raw dictionary validated to that model. Validation MUST require
`@context`, `@graph`, a root data entity with `@id: "./"`, and a non-empty trimmed `identifier`; it is structural
validation only and MUST NOT parse with arctrl on the ingest path. `identifier`, `name`, and `description` MAY be JSON
strings, one-element string arrays, or JSON-LD value objects; optional `name` and `description` SHALL remain unchanged
in `@graph` while being exposed read-only.

#### Scenario: Reject an invalid wire payload

- **GIVEN** an ARC without a valid RO-Crate structure
- **WHEN** an HTTP caller submits it
- **THEN** the caller receives `422 Unprocessable Entity`

#### Scenario: Defer arctrl semantic parsing

- **GIVEN** a payload that passes `RoCratePayload` but arctrl cannot parse
- **WHEN** it is ingested
- **THEN** it is stored and the later worker sync fails permanently rather than returning HTTP `422`

### Requirement: Persist and classify ARC ingestion

The system SHALL persist each validated ARC through `DocumentStore.store_arc` and return its identifier, `CREATED` or
`UPDATED` status, timestamp, originating `rdi`, and caller `client_id`. It MUST report `CREATED` for a new record,
`UPDATED` for changed content, and idempotent `UPDATED` for identical content. An identical standalone re-submit MUST
refresh `last_seen` as applicable but MUST NOT write the ARC body or schedule sync.

#### Scenario: Update changed standalone content

- **GIVEN** an existing `(identifier, rdi)` record
- **WHEN** standalone ingestion submits different content
- **THEN** the record is updated and reports `UPDATED`

#### Scenario: Prevent duplicate identity documents

- **GIVEN** any success or conflict path for an `(identifier, rdi)` key
- **WHEN** ingestion completes
- **THEN** at most one ARC document exists for that key

### Requirement: Dispatch sync only for new or changed content

The system SHALL schedule background Git sync if and only if the ARC is new or changed. During sync it MUST delegate Git
persistence to `arc-store/`, which derives human-readable Git metadata from the parsed arctrl ARC. ARC payloads sent to
Celery MUST be JSON dictionaries, not arctrl `ARC` objects; the worker MUST revalidate queued JSON with `parse_rocrate`
and parse it with arctrl before syncing.

#### Scenario: Avoid redundant sync

- **GIVEN** an identical ARC re-submission
- **WHEN** document storage reports no content change
- **THEN** no second background sync is scheduled

### Requirement: Record harvest context

When provided a harvest context, the system SHALL record `last_harvest_id` on the ARC document and SHALL set
`first_harvest_id` and `last_changed_harvest_id` when applicable. It MUST NOT increment harvest counters per ingest;
`harvest-manager/` derives counters at finalization with `get_harvest_statistics`.

#### Scenario: Ingest with harvest context

- **GIVEN** a valid ARC and `harvest_id`
- **WHEN** it is stored
- **THEN** the ARC document carries the applicable harvest metadata

### Requirement: Enforce harvest-scoped immutable identity

Within a harvest, an identical re-submit for an already recorded identifier and content hash SHALL return idempotent
`UPDATED`, without a second document or sync. A re-submit of that identifier with a different hash MUST raise
`DuplicateArcError`, leave the stored document unchanged, and be mapped by harvest callers to
`DuplicateArcInHarvestError` and HTTP `409`.

#### Scenario: Retry an identical harvest submission

- **GIVEN** an identifier already recorded in a harvest with identical content
- **WHEN** the client re-submits it after a lost response
- **THEN** it succeeds with `UPDATED` and HTTP `200`

#### Scenario: Reject conflicting harvest content

- **GIVEN** an identifier already recorded in a harvest
- **WHEN** the client submits different content
- **THEN** `DuplicateArcError` is raised and the document body and hash remain unchanged

#### Scenario: Submit concurrently with identical content

- **GIVEN** two concurrent identical submissions for one identifier and harvest
- **WHEN** both ingestion operations finish
- **THEN** both observe `CREATED` or `UPDATED`, no `DuplicateArcError` occurs, and at most one document exists

### Requirement: Map pipeline outcomes for HTTP callers

`arc-upload/` and `harvest-arc-upload/` SHALL map success, including identical harvest retries, to `200 OK`; structural
`RoCratePayload` or `InvalidJsonSemanticError` failures to `422`; harvest duplicate conflicts to `409`; and unexpected
`BusinessLogicError` failures or a missing post-store metadata record to `500 Internal Server Error`.

#### Scenario: Handle a pipeline failure

- **GIVEN** an unexpected pipeline error
- **WHEN** an HTTP endpoint invokes the pipeline
- **THEN** the error is wrapped and mapped to HTTP `500`
