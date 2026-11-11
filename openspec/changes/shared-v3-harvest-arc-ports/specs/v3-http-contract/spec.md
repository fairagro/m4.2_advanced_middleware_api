# Spec Delta

## Purpose

Defines the shared `/v3` harvest and ARC HTTP contract surface (route registration and operation port) used by both
production Middleware API and the local-offline stand-in for the ApiClient harvest lifecycle.

## ADDED Requirements

### Requirement: Shared lifecycle route surface

The system MUST provide a single FastAPI route registration for the ApiClient harvest lifecycle that both production and
local-offline applications mount. That surface MUST include create harvest, get harvest, patch harvest to a terminal
client status, submit ARC in harvest, complete harvest, standalone ARC upload, and a successful liveness probe. Routes
MUST use the shared v3 API models for request/response contracts where responses are structured.

#### Scenario: Both apps expose the same lifecycle paths

- **GIVEN** a production API app and a local-offline stand-in app built for the same release
- **WHEN** their HTTP route tables are compared for the ApiClient harvest lifecycle
- **THEN** both expose the same paths and HTTP methods for that lifecycle
- **AND** structured lifecycle responses use the shared v3 response models

### Requirement: Operation port separates backends

Shared lifecycle routers MUST invoke harvest and ARC operations only through an application-supplied operation port.
Production and local-offline MUST each supply their own port implementation. The shared route layer MUST NOT import the
production `api` package.

#### Scenario: Offline mounts without production api

- **GIVEN** an environment with the shared v3 HTTP package and local-offline installed
- **AND** package `api` is not installed
- **WHEN** the local-offline app factory builds an ASGI app using the shared routers and an offline port
- **THEN** the app starts and serves the lifecycle surface

#### Scenario: Production keeps strict semantics in its port

- **GIVEN** the production API mounted on the shared lifecycle routers
- **WHEN** a harvest-scoped ARC submit hits a true content or identity conflict
- **THEN** the production port still yields the production HTTP conflict behaviour required by harvest-arc-upload
- **AND** that behaviour is not required of the offline port

### Requirement: Single calculate_arc_id implementation

ARC document identity hashing for identifier+RDI MUST be implemented once in `middleware.shared` and MUST be the only
implementation used by production API and the local-offline stand-in.

#### Scenario: Prod and offline share identity hashing

- **GIVEN** the same identifier and RDI strings (including surrounding whitespace subject to strip-only rules)
- **WHEN** production code and local-offline code compute `arc_id`
- **THEN** both produce the identical `arc_id` string from the shared implementation
