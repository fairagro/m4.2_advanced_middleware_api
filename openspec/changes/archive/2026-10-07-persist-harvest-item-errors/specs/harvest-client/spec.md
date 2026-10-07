# Spec Delta

## ADDED Requirements

### Requirement: Surface server-persisted harvest errors

When a harvest query or completed-harvest response includes a server `errors` list, the client MUST expose those entries
on `HarvestResult.errors` using the existing typed error model.

#### Scenario: Map server errors after harvest completion

- **GIVEN** the server completed-harvest response contains one or more per-item errors
- **WHEN** the client returns its harvest result
- **THEN** those errors appear on `HarvestResult.errors`

## MODIFIED Requirements

### Requirement: Collect typed per-item errors

The result MUST include an errors list containing every item-level submission error observed by the client **and** every
per-item error returned by the server for that harvest. Each error MUST provide a category, a human-readable message, an
ISO 8601 occurrence timestamp, and an optional ARC identifier. Until the server records every client-observed failure
mode, the client MUST continue to collect errors during parallel submission and MUST merge them with server-provided
errors so callers still see a complete list.

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
