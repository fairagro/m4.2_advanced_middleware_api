# Spec Delta

## ADDED Requirements

### Requirement: Record harvest item errors on conflict responses

When harvest-scoped ARC upload rejects a request with HTTP `409` because of a harvest-local content conflict or an
`arc_id` identity mismatch, the system MUST append a corresponding typed per-item error to the harvest document before
or as part of returning that `409`. Identical-content re-submits that return HTTP `200` MUST NOT append a duplicate
error. This requirement MUST NOT weaken **Remain retry-safe for identical harvest content**: successful identical
retries stay HTTP `200` and MUST NOT be reclassified as conflicts solely to record a `duplicate` error.

#### Scenario: Content conflict appends a duplicate error

- **GIVEN** an ARC identifier already submitted to this harvest with different content
- **WHEN** a conflicting body is submitted
- **THEN** the response remains HTTP `409 Conflict`
- **AND** the harvest document gains an error with category `duplicate` for that ARC identifier

#### Scenario: Identity mismatch appends a submission_failed error

- **GIVEN** an existing `arc_{arc_id}` whose stored identifier or `rdi` does not match the incoming pair
- **WHEN** the harvest client submits that ARC
- **THEN** the response remains HTTP `409 Conflict`
- **AND** the harvest document gains an error with category `submission_failed`

#### Scenario: Identical retry does not append an error

- **GIVEN** an ARC identifier already submitted to this harvest with identical content
- **WHEN** it is re-submitted
- **THEN** the response remains HTTP `200`
- **AND** no new per-item error is appended for that retry

## MODIFIED Requirements

### Requirement: Remain retry-safe for identical harvest content

The harvest-scoped ARC upload endpoint MUST be retry-safe: when the same ARC identifier is submitted again to the same
harvest with content that matches the already stored ARC for that harvest, the system MUST treat the request as a
successful idempotent retry. It MUST return HTTP `200` with an `UPDATED` outcome, MUST NOT create a second document,
MUST NOT schedule a second sync, and MUST NOT reject that request with HTTP `409` solely because the identifier was
already seen in this harvest. HTTP `409` is reserved for true conflicts (different content for the same identifier in
this harvest, or `arc_id` identity mismatch). Persisting per-item harvest errors MUST NOT change these status codes or
turn identical-content retries into conflicts.

#### Scenario: Lost-response retry of identical content succeeds

- **GIVEN** an ARC identifier already submitted to this harvest with identical content
- **WHEN** the client re-submits the same body after a lost response or transport failure
- **THEN** the response is HTTP `200` with `UPDATED`
- **AND** no second document is created
- **AND** no second sync is scheduled
- **AND** the response is not HTTP `409`

#### Scenario: Error persistence does not reclassify identical retries

- **GIVEN** an ARC identifier already submitted to this harvest with identical content
- **WHEN** it is re-submitted while the server records per-item harvest errors on true `409` conflicts
- **THEN** the retry still returns HTTP `200` with `UPDATED`
- **AND** no `duplicate` error is appended for that retry
