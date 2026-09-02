# Document Store — Delta

## MODIFIED Requirements

### Requirement: Manage harvest data, events, and resources

The store SHALL create, retrieve, calculate statistics for, and update harvest documents, including terminal
transitions. Harvest statistics MUST include every ARC document whose `metadata.last_harvest_id` matches the
harvest being finalized, regardless of how many documents match. The store MUST NOT cap statistics at
`default_query_limit` from a single Mango `_find` page. It MUST append ARC event records and release its HTTP
session and database client at shutdown. An unknown harvest lookup SHALL return nothing so callers can raise
`ResourceNotFoundError`.

#### Scenario: Shut down the store

- **GIVEN** a connected document store
- **WHEN** it shuts down
- **THEN** the underlying HTTP session and database client are released

#### Scenario: Statistics beyond default query limit

- **GIVEN** more than `default_query_limit` ARC documents with the same `metadata.last_harvest_id`
- **WHEN** `get_harvest_statistics` runs for that harvest
- **THEN** `arcs_submitted` equals the total number of matching ARC documents
- **AND** `arcs_new`, `arcs_updated`, and `arcs_unchanged` sum to that total using the existing classification
  rules
