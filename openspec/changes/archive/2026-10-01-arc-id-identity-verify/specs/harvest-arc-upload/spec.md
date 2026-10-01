# Harvest-Context ARC Upload — Delta

## ADDED Requirements

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
