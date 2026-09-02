# Harvest Manager — Delta

## ADDED Requirements

### Requirement: Surface partial-push skips on catalog success events

When the worker records a harvest catalog success event (`CATALOG_PUSH_SUCCESS`)
after consolidated catalog finalize, and the finalize outcome reports one or
more skipped ARCs, the event message MUST include the number of Datasets
included, the number of skips, and a bounded list of skipped `arc_id` values so
operators can see omissions without reading worker logs. When there are no
skips, the success message MAY omit skip details. Permanent finalize failures
continue to record `CATALOG_PUSH_FAILED` as today. The system MUST NOT add a
new catalog event type solely for partial success in this change.

#### Scenario: Success event mentions skipped ARCs

- **GIVEN** a harvest-scoped catalog finalize that published (or left unchanged)
  a catalog while skipping one or more ARCs
- **WHEN** the worker appends `CATALOG_PUSH_SUCCESS` to that harvest
- **THEN** the event message includes the skip count and at least one skipped
  `arc_id`

#### Scenario: Success with no skips stays concise

- **GIVEN** a harvest-scoped catalog finalize with zero skipped ARCs
- **WHEN** the worker appends `CATALOG_PUSH_SUCCESS`
- **THEN** the event type remains `CATALOG_PUSH_SUCCESS`
- **AND** the message still indicates publish or unchanged outcome for the RDI
