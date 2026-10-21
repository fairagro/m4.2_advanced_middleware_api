# Spec Delta

## ADDED Requirements

### Requirement: Bound harvest catalog events

When a harvest update appends a catalog event, the stored catalog-event list MUST contain at most the configured maximum
number of entries. The maximum MUST default to 100 when unset. The update MUST retain the newest entries, including the
event just appended, and MUST drop the oldest entries that do not fit. Entries that fit MUST keep their existing order.
A harvest update that does not append a catalog event MUST leave the stored list unchanged.

#### Scenario: Append past the maximum drops the oldest event

- **GIVEN** a harvest whose stored catalog events already number the configured maximum
- **WHEN** a harvest update appends one more catalog event
- **THEN** the stored list length equals that maximum
- **AND** the newest entry is the event just appended
- **AND** the oldest event from before the update is absent

#### Scenario: Append under the maximum keeps prior events

- **GIVEN** a harvest whose stored catalog events number less than the configured maximum
- **WHEN** a harvest update appends one catalog event
- **THEN** every previously stored catalog event remains
- **AND** the appended event is the last entry

#### Scenario: Default maximum is 100

- **GIVEN** a harvest with 100 stored catalog events and no operator override of the maximum
- **WHEN** a harvest update appends one catalog event
- **THEN** the stored list contains 100 events
- **AND** the appended event is kept
