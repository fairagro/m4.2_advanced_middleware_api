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

### Requirement: Reject standalone upload when consolidated Git store is configured

When the deployment’s ArcStore backend is the consolidated Git catalog store,
standalone ARC create endpoints (`POST /v1/arcs`, `POST /v2/arcs`, and
`POST /v3/arcs`) SHALL reject the request with HTTP `400` (or another documented
4xx) before staging content in CouchDB or scheduling Git sync. Harvest-scoped
ARC submission (`POST /v3/harvests/{harvest_id}/arcs`) remains the supported
ingestion path for that backend.

#### Scenario: Standalone ARC rejected under consolidated store

- **GIVEN** `consolidated_git` is the configured ArcStore backend
- **WHEN** a client calls `POST /v1/arcs`, `POST /v2/arcs`, or `POST /v3/arcs`
- **THEN** the API returns HTTP `400` and does not stage or publish catalog
  content for that request
