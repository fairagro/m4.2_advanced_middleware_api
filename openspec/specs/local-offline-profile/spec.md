# local-offline-profile Specification

## Purpose

Defines a publishable local offline Middleware stand-in so harvester and sql-to-arc can obtain ARCs on disk for output
tests without CouchDB, RabbitMQ, or DataHUB. HTTP behaviour beyond what `ApiClient` needs to finish a harvest is out of
scope.

## Requirements

### Requirement: Ship as fairagro-middleware-api-local-offline

The local offline stand-in MUST be distributed as the PyPI package `fairagro-middleware-api-local-offline` from
workspace path `middleware/api_local_offline`, without depending on the Middleware `api` package. It MUST expose a
console script `middleware-api-local-offline` and an in-process app factory for ASGI test use.

#### Scenario: Install without api package

- **GIVEN** a clean environment
- **WHEN** `fairagro-middleware-api-local-offline` is installed
- **THEN** the stand-in CLI and app factory are importable without installing package `api`

### Requirement: Select local offline stand-in at process start

The stand-in process MUST refuse to start if a production CouchDB document-store configuration, a message-broker URL for
Celery, or a Git/DataHUB remote ArcStore configuration is present in its config. When inactive (not run), production API
startup is unchanged.

#### Scenario: Offline stand-in starts without production backends

- **GIVEN** a local offline config with only stand-in fields (including output root)
- **WHEN** the stand-in process starts
- **THEN** startup succeeds

#### Scenario: Offline stand-in rejects mixed production backends

- **GIVEN** a config that also contains CouchDB, Celery broker, or Git ArcStore keys
- **WHEN** the stand-in loads that config
- **THEN** startup fails before serving requests

### Requirement: Enough HTTP for ApiClient harvest lifecycle

The stand-in MUST expose HTTP operations sufficient for `ApiClient.harvest_arcs` and related helpers: create harvest,
get harvest, submit ARC in harvest, complete harvest, patch harvest to `FAILED` or `CANCELLED`, standalone
`POST /v3/arcs`, and a successful liveness probe. Responses MUST be parseable by `ApiClient`. Production conflict or
identity HTTP semantics are NOT required.

#### Scenario: Client harvest lifecycle completes offline

- **GIVEN** a running local offline stand-in
- **WHEN** a client creates a harvest, submits one or more ARCs, and completes the harvest
- **THEN** each step returns responses `ApiClient` can parse
- **AND** the harvest run reaches a completed success outcome for that client flow

### Requirement: Write accepted ARCs to the output root before responding

A successful ARC submit MUST write the ARC under the configured output root as part of the same request and MUST NOT
return success until that write has finished or failed. A failed on-disk write MUST surface as a server error. The
output root MUST be configurable.

#### Scenario: Submit writes ARC files before HTTP success

- **GIVEN** the stand-in with a configured output root
- **WHEN** a client successfully submits an ARC
- **THEN** the ARC is present under the output root before the HTTP success response is returned

#### Scenario: Disk write failure is not a successful submit

- **GIVEN** the stand-in
- **AND** the filesystem write fails
- **WHEN** a client submits that ARC
- **THEN** the API returns a server error
- **AND** the client MUST NOT treat the ARC as successfully created

### Requirement: Offline health does not require broker or Git

Readiness and liveness checks MUST NOT require a message broker or Git/DataHUB connectivity. Readiness MAY require that
the configured output root is usable for writes.

#### Scenario: Liveness without broker

- **GIVEN** the stand-in with no broker configured
- **WHEN** a liveness probe is requested
- **THEN** the probe succeeds without contacting RabbitMQ or DataHUB
