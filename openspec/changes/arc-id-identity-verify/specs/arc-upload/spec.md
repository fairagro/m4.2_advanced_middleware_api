# Standalone ARC Upload — Delta

## ADDED Requirements

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
