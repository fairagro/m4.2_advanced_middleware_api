# Harvest-Context ARC Upload

## Purpose

`POST /v3/harvests/{harvest_id}/arcs` submits an ARC for an ongoing harvest. The endpoint resolves its RDI from the
harvest, delegates to `arc-manager/`, and MUST remain retry-safe for identical content within that harvest.

## Requirements

### Requirement: Remain retry-safe for identical harvest content

The harvest-scoped ARC upload endpoint MUST be retry-safe: when the same ARC identifier is submitted again to the same
harvest with content that matches the already stored ARC for that harvest, the system MUST treat the request as a
successful idempotent retry. It MUST return HTTP `200` with an `UPDATED` outcome, MUST NOT create a second document,
MUST NOT schedule a second sync, and MUST NOT reject that request with HTTP `409` solely because the identifier was
already seen in this harvest. HTTP `409` is reserved for true conflicts (different content for the same identifier in
this harvest, or `arc_id` identity mismatch). Changes that would make a second identical-content submit return `409` are
forbidden — they would break lost-response and transport retries.

#### Scenario: Lost-response retry of identical content succeeds

- **GIVEN** an ARC identifier already submitted to this harvest with identical content
- **WHEN** the client re-submits the same body after a lost response or transport failure
- **THEN** the response is HTTP `200` with `UPDATED`
- **AND** no second document is created
- **AND** no second sync is scheduled
- **AND** the response is not HTTP `409`

### Requirement: Resolve and authorize the harvest context

The endpoint SHALL accept `harvest_id` and `SubmitHarvestArcRequest` containing a `RoCratePayload` `arc` but no `rdi`.
It MUST load the harvest, resolve its RDI, and verify that the RDI is known and authorized for the client before
delegating with `harvest_id`.

#### Scenario: Reject a missing harvest

- **GIVEN** an unknown `harvest_id`
- **WHEN** the endpoint receives a submission
- **THEN** it returns HTTP `404` and never resolves an RDI

#### Scenario: Reject an invalid resolved RDI

- **GIVEN** a harvest whose RDI is not in `known_rdis`
- **WHEN** the endpoint processes a submission
- **THEN** it returns HTTP `400`

#### Scenario: Reject an unauthorized resolved RDI

- **GIVEN** a harvest RDI known to the deployment but unauthorized for the client
- **WHEN** the endpoint processes a submission
- **THEN** it returns HTTP `403`

### Requirement: Return harvest-scoped ARC results

On successful ingestion, including an idempotent retry under **Remain retry-safe for identical harvest content**, the
endpoint SHALL fetch current ARC metadata and return HTTP `200` with an `ArcResponse` containing `client_id`, `arc_id`,
`status`, hashes and timestamps, and the current event log. It MUST apply the HTTP mapping in `arc-manager/`, including
harvest-scoped conflicts.

#### Scenario: Reject conflicting harvest content

- **GIVEN** an ARC identifier already submitted to this harvest
- **WHEN** the request carries different content
- **THEN** it returns HTTP `409 Conflict` as `DuplicateArcInHarvestError` and does not change the existing document

#### Scenario: Handle shared failures

- **GIVEN** a wire-validation failure, worker arctrl parse failure, metadata fetch failure, or pipeline error
- **WHEN** the endpoint processes the request
- **THEN** it follows the applicable `arc-manager/` contract

### Requirement: Reject arc_id identity mismatch in harvest

When harvest-scoped ingestion finds an existing `arc_{arc_id}` whose stored identifier or `rdi` does not match the
incoming pair under strip-only rules, the endpoint MUST return HTTP `409 Conflict`, MUST NOT overwrite the stored
document, and MUST NOT schedule sync for that attempt. This is distinct from the existing harvest-local
duplicate-content conflict (`DuplicateArcInHarvestError`), though both map to `409`.

#### Scenario: Conflict on colliding identity within a harvest

- **GIVEN** an ARC document already stored at `arc_{arc_id}` with a different stripped identifier or `rdi`
- **WHEN** a harvest client submits an ARC that hashes to the same `arc_id`
- **THEN** the response is HTTP `409 Conflict`
- **AND** the existing document is unchanged
- **AND** no sync is scheduled for the rejected attempt
