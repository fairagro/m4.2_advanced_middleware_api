# Spec Delta — harvest-client

## MODIFIED Requirements

### Requirement: Collect typed per-item errors

The result MUST include an errors list containing every item-level submission error observed by the client **and** every
per-item error returned by the server for that harvest. Each error MUST provide a category, a human-readable message, an
ISO 8601 occurrence timestamp, and an optional ARC identifier. The client MUST collect errors during parallel submission
(including durable client-only modes such as intra-batch duplicate skips that never reach the server) and MUST merge
them with server-provided errors so callers see a complete list.

#### Scenario: Return a successful harvest with no item errors

- **GIVEN** all ARC submissions succeed and the server reports no errors
- **WHEN** the completed result is returned
- **THEN** its errors list is empty

#### Scenario: Record an error without an extractable ARC identifier

- **GIVEN** an ARC has no extractable RO-Crate identifier and its submission produces an error
- **WHEN** the client records that error
- **THEN** the error has no ARC identifier

#### Scenario: Merge client-collected and server-persisted errors

- **GIVEN** the client recorded item errors during submission and the completed harvest response also includes errors
- **WHEN** the client returns its harvest result
- **THEN** the errors list includes both sets

### Requirement: Detect duplicate identifiers before submission

The client MUST detect duplicate ARC identifiers within one `harvest_arcs` batch before making the duplicate request,
skip the later ARC, and record a `duplicate` error. The first ARC with that identifier MUST continue through normal
submission. This intra-batch skip and client-side `duplicate` reporting is durable client policy (producer-side
duplicate identifiers in one batch), not a temporary shim pending server changes.

#### Scenario: Skip the second ARC with a duplicate identifier

- **GIVEN** two submitted ARCs share an identifier
- **WHEN** the client processes the batch
- **THEN** it submits the first ARC, skips the second, and records a `duplicate` error for the second ARC
