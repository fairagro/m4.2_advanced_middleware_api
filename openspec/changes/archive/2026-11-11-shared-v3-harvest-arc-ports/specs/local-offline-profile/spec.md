# Spec Delta

## MODIFIED Requirements

### Requirement: Ship as fairagro-middleware-api-local-offline

The local offline stand-in MUST be distributed as the PyPI package `fairagro-middleware-api-local-offline` from
workspace path `middleware/api_local_offline`, without depending on the Middleware `api` package. It MAY depend on the
shared v3 HTTP contract package and `fairagro-middleware-shared`. It MUST expose a console script
`middleware-api-local-offline` and an in-process app factory for ASGI test use.

#### Scenario: Install without api package

- **GIVEN** a clean environment
- **WHEN** `fairagro-middleware-api-local-offline` is installed
- **THEN** the stand-in CLI and app factory are importable without installing package `api`

### Requirement: Enough HTTP for ApiClient harvest lifecycle

The stand-in MUST expose HTTP operations sufficient for `ApiClient.harvest_arcs` and related helpers by mounting the
shared `v3-http-contract` lifecycle route surface with an offline operation port: create harvest, get harvest, submit
ARC in harvest, complete harvest, patch harvest to `FAILED` or `CANCELLED`, standalone `POST /v3/arcs`, and a successful
liveness probe. Responses MUST be parseable by `ApiClient`. Production conflict or identity HTTP semantics are NOT
required and MUST remain offline-adapter-local.

#### Scenario: Client harvest lifecycle completes offline

- **GIVEN** a running local offline stand-in
- **WHEN** a client creates a harvest, submits one or more ARCs, and completes the harvest
- **THEN** each step returns responses `ApiClient` can parse
- **AND** the harvest run reaches a completed success outcome for that client flow

#### Scenario: Offline uses shared lifecycle routers

- **GIVEN** a running local offline stand-in
- **WHEN** the stand-in’s route table is inspected for the ApiClient harvest lifecycle
- **THEN** those routes come from the shared v3 HTTP contract registration
- **AND** the stand-in does not register a parallel hand-rolled duplicate of that lifecycle surface
