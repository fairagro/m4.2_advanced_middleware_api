# Spec Delta

## ADDED Requirements

### Requirement: Persist per-item harvest errors

The harvest document MUST store a list of typed per-item errors. Each error MUST include an error category (`duplicate`
or `submission_failed`), a human-readable message, an ISO 8601 timestamp, and an optional ARC identifier (RO-Crate
identifier, not content hash). Missing `errors` on existing documents MUST be treated as an empty list.

#### Scenario: Load a legacy harvest without errors

- **GIVEN** a CouchDB harvest document with no `errors` field
- **WHEN** it is loaded
- **THEN** the harvest exposes an empty errors list

#### Scenario: Retrieve a harvest that recorded item errors

- **GIVEN** a harvest document that contains one or more per-item errors
- **WHEN** the harvest is retrieved or listed
- **THEN** the API response includes those errors in an `errors` field

### Requirement: Expose harvest errors on the wire

`HarvestResponse` MUST include an `errors` list with the same shape as the stored per-item errors. When no errors were
recorded, the field MUST be an empty list (not omitted in a way that breaks typed clients that expect a list after this
change — default empty is required).

#### Scenario: GET harvest returns empty errors

- **GIVEN** a harvest with no recorded item errors
- **WHEN** a client GETs the harvest
- **THEN** the response contains `errors` as an empty list
