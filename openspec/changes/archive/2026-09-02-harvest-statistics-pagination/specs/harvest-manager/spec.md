# Harvest Manager — Delta

## MODIFIED Requirements

### Requirement: Derive and persist terminal statistics

When finalizing, the system SHALL derive statistics through `DocumentStore.get_harvest_statistics` for ARC
documents with matching `metadata.last_harvest_id`. It MUST classify them as new, updated, or unchanged with
`first_harvest_id` and `last_changed_harvest_id`, mark the harvest complete, and record the resulting snapshot.
Statistics MUST be complete for harvests whose ARC count exceeds the document store's default query page size.

#### Scenario: Finalize before all uploads arrive

- **GIVEN** a harvest whose expected uploads are incomplete
- **WHEN** it is finalized
- **THEN** it completes with the statistics currently available and does not enforce `expected_datasets`

#### Scenario: Finalize a large harvest

- **GIVEN** a harvest with more ARC submissions than `default_query_limit`
- **WHEN** the harvest transitions to a terminal status
- **THEN** persisted `statistics.arcs_submitted` equals the number of ARC documents last seen in that harvest
- **AND** the new/updated/unchanged breakdown matches the full set, not only the first query page
