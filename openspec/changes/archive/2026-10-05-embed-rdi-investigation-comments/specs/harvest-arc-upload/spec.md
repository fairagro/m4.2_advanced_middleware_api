# Spec Delta

## ADDED Requirements

### Requirement: Reject conflicting Investigation Comment[RDI] on harvest upload

When the shared ingestion pipeline rejects an ARC because Investigation `Comment[RDI]` disagrees with the harvest’s
resolved RDI, the endpoint MUST return HTTP `422 Unprocessable Entity`, MUST NOT overwrite any stored document, and MUST
NOT schedule Git sync for that attempt. The harvest document RDI remains authoritative for authorization.

#### Scenario: Harvest Comment[RDI] conflict

- **GIVEN** an ongoing harvest whose RDI is `edal`
- **AND** a client authorized for that harvest
- **AND** a submit body whose ARC Investigation Comment `RDI` is `edaphobase`
- **WHEN** the client calls `POST /v3/harvests/{harvest_id}/arcs`
- **THEN** the response is HTTP `422 Unprocessable Entity`
- **AND** no document write or sync is performed for that attempt
