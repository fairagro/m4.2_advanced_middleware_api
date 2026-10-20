## ADDED Requirements

### Requirement: Reject harvest-scoped ARC submit when harvest is not RUNNING

After the harvest document is loaded and before RDI authorization succeeds into `create_or_update_arc`, the
harvest-scoped ARC upload endpoint MUST require `harvest.status == RUNNING`. When the harvest is `COMPLETED`,
`CANCELLED`, `FAILED`, or any other non-`RUNNING` status, the endpoint MUST return HTTP `409 Conflict`, MUST NOT persist
ARC content for that attempt, MUST NOT enqueue Git sync for that attempt, and MUST NOT append a per-item harvest ARC
error solely for this lifecycle gate (distinct from harvest-local content / identity `409`s). The conflict detail MUST
allow operators to see that the harvest is not running (e.g. include the current status).

#### Scenario: Reject submit on COMPLETED harvest

- **GIVEN** a harvest already in `COMPLETED`
- **WHEN** a client calls `POST /v3/harvests/{harvest_id}/arcs`
- **THEN** the response is HTTP `409 Conflict`
- **AND** no ARC document write or Git sync enqueue occurs for that attempt

#### Scenario: Reject submit on CANCELLED or FAILED harvest

- **GIVEN** a harvest in `CANCELLED` or `FAILED`
- **WHEN** a client submits an ARC to that harvest
- **THEN** the response is HTTP `409 Conflict`

#### Scenario: Allow submit while RUNNING

- **GIVEN** a harvest in `RUNNING`
- **WHEN** a client submits a valid ARC
- **THEN** processing continues under existing harvest-arc-upload and arc-manager rules (including identical-content
  retry `200`)
