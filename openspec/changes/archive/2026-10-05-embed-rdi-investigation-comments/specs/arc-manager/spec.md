# Spec Delta

## ADDED Requirements

### Requirement: Embed authorized source RDI as Investigation Comments

After structural RO-Crate validation and before document persist and content-hash comparison, the ingestion pipeline
SHALL ensure the ARC Investigation carries these ISA Comment names with values derived from the authorized ingest RDI
and the deployment RDI registry:

| Comment name      | Value source                                                        |
| ----------------- | ------------------------------------------------------------------- |
| `RDI`             | Authorized ingest RDI identifier (request body or harvest document) |
| `RDI Description` | Registry description for that RDI (empty string when unset)         |
| `RDI URL`         | Registry canonical URL for that RDI (empty string when unset)       |

The pipeline MUST create missing Comments and MUST overwrite `RDI Description` and `RDI URL` from the registry on every
successful enrichment. The enriched RO-Crate body MUST be the body stored in the document store and, when sync is
scheduled, the body queued for Git sync, so Git `arc.Write()` materializes the Comments in `isa.investigation.xlsx`.

#### Scenario: Inject Comments when absent

- **GIVEN** a valid ARC without Investigation Comments named `RDI`, `RDI Description`, or `RDI URL`
- **AND** an authorized ingest RDI present in the deployment registry
- **WHEN** the ARC is ingested
- **THEN** the stored ARC body includes those three Comments with the authorized identifier and registry description/URL
- **AND** a scheduled Git sync uses that same enriched body

#### Scenario: Overwrite Description and URL from registry

- **GIVEN** a valid ARC whose Investigation already has `RDI Description` or `RDI URL` values that differ from the
  registry
- **AND** `Comment[RDI]` is absent or matches the authorized ingest RDI
- **WHEN** the ARC is ingested
- **THEN** the stored Comments use the registry description and URL for that RDI

#### Scenario: Idempotent re-submit after enrichment

- **GIVEN** a prior successful ingest that stored an enriched ARC for `(identifier, rdi)`
- **WHEN** the client re-submits the same logical ARC (with or without the three Comments already present, matching the
  registry after enrichment)
- **THEN** document storage reports no content change
- **AND** no second Git sync is scheduled

### Requirement: Reject conflicting Comment[RDI]

When the ARC Investigation already contains a Comment named `RDI` whose value (after trim) is non-empty and differs from
the authorized ingest RDI, the pipeline MUST reject the ingest without persisting a new body or scheduling Git sync. The
failure MUST be mapped for HTTP callers as `422 Unprocessable Entity` under the shared outcome mapping (same class of
outcome as semantic JSON / RO-Crate validation failures).

#### Scenario: Conflict with authorized RDI

- **GIVEN** an authorized ingest RDI `edal`
- **AND** an ARC Investigation Comment `RDI` with value `edaphobase`
- **WHEN** the ARC is ingested
- **THEN** the pipeline rejects the operation
- **AND** the stored document (if any) is unchanged
- **AND** no Git sync is scheduled for that attempt

#### Scenario: Matching Comment[RDI] accepted

- **GIVEN** an authorized ingest RDI `edal`
- **AND** an ARC Investigation Comment `RDI` with value `edal`
- **WHEN** the ARC is ingested
- **THEN** enrichment proceeds and `Comment[RDI]` remains `edal`

## MODIFIED Requirements

### Requirement: Map pipeline outcomes for HTTP callers

`arc-upload/` and `harvest-arc-upload/` SHALL map success, including identical harvest retries, to `200 OK`; structural
`RoCratePayload` or `InvalidJsonSemanticError` failures to `422`; conflicting Investigation `Comment[RDI]` versus the
authorized ingest RDI to `422`; harvest duplicate-content conflicts to `409`; `arc_id` identity-mismatch conflicts
(strip-only stored vs incoming identifier/`rdi`) to `409`; and unexpected `BusinessLogicError` failures or a missing
post-store metadata record to `500 Internal Server Error`.

#### Scenario: Handle a pipeline failure

- **GIVEN** an unexpected pipeline error
- **WHEN** an HTTP endpoint invokes the pipeline
- **THEN** the error is wrapped and mapped to HTTP `500`

#### Scenario: Map identity mismatch to HTTP 409

- **GIVEN** document storage raises an identity conflict for an existing `arc_{arc_id}`
- **WHEN** a standalone or harvest-scoped HTTP endpoint invokes the pipeline
- **THEN** the caller receives HTTP `409 Conflict` and the stored document is unchanged

#### Scenario: Map Comment[RDI] conflict to HTTP 422

- **GIVEN** the pipeline rejects an ARC because Investigation `Comment[RDI]` disagrees with the authorized ingest RDI
- **WHEN** a standalone or harvest-scoped HTTP endpoint invokes the pipeline
- **THEN** the caller receives HTTP `422 Unprocessable Entity`
- **AND** the stored document is unchanged
