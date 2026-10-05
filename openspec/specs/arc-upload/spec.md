# Standalone ARC Upload

## Purpose

`POST /v3/arcs` accepts one ARC outside a harvest, with its `rdi` supplied by the request body. It delegates processing
to `arc-manager/` and is safe to retry for the same `(identifier, rdi)`.

## Requirements

### Requirement: Accept a standalone ARC request

The endpoint SHALL accept `CreateArcRequest` containing `rdi` and an `arc` conforming to the `RoCratePayload` contract
in `arc-manager/`. It MUST validate that the RDI is both known to the deployment and authorized for the requesting
client before delegating to the ingestion pipeline without harvest context.

#### Scenario: Reject an unknown RDI

- **GIVEN** a request with an RDI absent from `known_rdis`
- **WHEN** the endpoint receives it
- **THEN** it returns HTTP `400` without calling business logic

#### Scenario: Reject an unauthorized RDI

- **GIVEN** a known RDI not authorized for the client
- **WHEN** the endpoint receives it
- **THEN** it returns HTTP `403` without calling business logic

### Requirement: Return persisted ARC metadata

On successful ingestion, including an idempotent identical re-submit, the endpoint SHALL fetch the current ARC metadata
and return HTTP `200` with `ArcResponse` containing `client_id`, `arc_id`, `status`, metadata hashes and timestamps, and
the current event log. It MUST apply the shared HTTP outcome mapping in `arc-manager/`.

#### Scenario: Retry identical content

- **GIVEN** a prior standalone ARC with the same identifier, RDI, and content
- **WHEN** the client re-submits it
- **THEN** the response is HTTP `200` with `UPDATED`, one document exists, and no second sync is scheduled

#### Scenario: Update changed content

- **GIVEN** a prior standalone ARC with the same identifier and RDI
- **WHEN** the client submits different content
- **THEN** the response is HTTP `200` with `UPDATED`, the document is replaced, and a sync is scheduled

#### Scenario: Propagate shared validation and pipeline behavior

- **GIVEN** a RO-Crate validation error, worker arctrl failure, or pipeline error
- **WHEN** the request is processed
- **THEN** the endpoint follows the applicable behavior in `arc-manager/`

### Requirement: Reject arc_id identity mismatch

When standalone ingestion finds an existing `arc_{arc_id}` whose stored identifier or `rdi` does not match the incoming
pair under strip-only rules, the endpoint MUST return HTTP `409 Conflict`, MUST NOT overwrite the stored document, and
MUST NOT schedule a second sync for that attempt. This is distinct from a successful content update for a matching
identity.

#### Scenario: Conflict on colliding identity

- **GIVEN** a prior standalone ARC document at `arc_{arc_id}` with a different stripped identifier or `rdi`
- **WHEN** the client submits an ARC whose calculated `arc_id` collides with that document
- **THEN** the response is HTTP `409 Conflict`
- **AND** the existing document is unchanged
- **AND** no sync is scheduled for the rejected attempt

### Requirement: Standalone upload uses per-ARC store only

Standalone ARC create endpoints (`POST /v2/arcs` and `POST /v3/arcs`) MUST always be accepted when the API is otherwise
healthy. They MUST stage content and schedule per-ARC Git sync via the required `arc_store` slot. They MUST NOT publish
or finalize the consolidated RDI catalog. API models exposed in OpenAPI/Swagger MUST describe that standalone uploads
update the per-ARC store only and do not update the consolidated catalog.

#### Scenario: Standalone accepted with consolidated_store configured

- **GIVEN** both `arc_store` and `consolidated_store` are configured
- **WHEN** a client calls `POST /v3/arcs`
- **THEN** the API accepts the request (subject to normal validation)
- **AND** schedules per-ARC sync via `arc_store`
- **AND** does not enqueue catalog finalize for that request

### Requirement: Reject conflicting Investigation Comment[RDI] on standalone upload

When the shared ingestion pipeline rejects an ARC because Investigation `Comment[RDI]` disagrees with the request-body
`rdi`, the endpoint MUST return HTTP `422 Unprocessable Entity`, MUST NOT overwrite any stored document, and MUST NOT
schedule Git sync for that attempt. Authorization still uses request `rdi` and client certificates; ARC Comments MUST
NOT expand the set of RDIs a client may write.

#### Scenario: Standalone Comment[RDI] conflict

- **GIVEN** a client authorized for RDI `edal`
- **AND** a `CreateArcRequest` with `rdi: edal` whose ARC Investigation Comment `RDI` is `edaphobase`
- **WHEN** the client calls `POST /v3/arcs`
- **THEN** the response is HTTP `422 Unprocessable Entity`
- **AND** no document write or sync is performed for that attempt
