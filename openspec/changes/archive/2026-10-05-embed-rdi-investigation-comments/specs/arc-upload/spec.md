# Spec Delta

## ADDED Requirements

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
