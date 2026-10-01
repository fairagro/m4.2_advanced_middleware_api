# ARC Manager — Delta

## ADDED Requirements

### Requirement: Refuse arc_id identity collisions

When document storage reports that an existing `arc_{arc_id}` document's stored identity does not match the incoming
`(identifier, rdi)` under strip-only rules, the ingestion pipeline MUST NOT treat the operation as a successful update
or schedule Git sync. It MUST raise a conflict error distinct from harvest-scoped content duplicates, leaving the stored
document unchanged. A true cryptographic collision MUST be handled the same as an identity mismatch.

#### Scenario: Pipeline stops on identity mismatch

- **GIVEN** document storage refuses an update due to identity mismatch at `arc_{arc_id}`
- **WHEN** `create_or_update_arc` runs
- **THEN** a conflict error is raised to the caller
- **AND** no Git sync is scheduled for that attempt

## MODIFIED Requirements

### Requirement: Map pipeline outcomes for HTTP callers

`arc-upload/` and `harvest-arc-upload/` SHALL map success, including identical harvest retries, to `200 OK`; structural
`RoCratePayload` or `InvalidJsonSemanticError` failures to `422`; harvest duplicate-content conflicts to `409`; `arc_id`
identity-mismatch conflicts (strip-only stored vs incoming identifier/`rdi`) to `409`; and unexpected
`BusinessLogicError` failures or a missing post-store metadata record to `500 Internal Server Error`.

#### Scenario: Handle a pipeline failure

- **GIVEN** an unexpected pipeline error
- **WHEN** an HTTP endpoint invokes the pipeline
- **THEN** the error is wrapped and mapped to HTTP `500`

#### Scenario: Map identity mismatch to HTTP 409

- **GIVEN** document storage raises an identity conflict for an existing `arc_{arc_id}`
- **WHEN** a standalone or harvest-scoped HTTP endpoint invokes the pipeline
- **THEN** the caller receives HTTP `409 Conflict` and the stored document is unchanged
