# Spec Delta

## ADDED Requirements

### Requirement: Unique Comment names per holder before Git Write

Immediately before materializing an ARC into a Git working tree via `ARC.Write`, the Git store SHALL ensure that each
Comment holder — Investigation (ARC root comments), Study, Assay, Person, and Publication — has at most one Comment per
Comment name. When multiple Comments share a name on the same holder, the store MUST keep the last Comment for that name
(last-wins) and MUST emit a warning log that names the holder kind, holder identity when available, and the duplicated
Comment name. Same Comment names on different holders MUST remain allowed. This normalisation MUST NOT run as part of
HTTP ingest, document-store persist, or `content_hash` computation.

#### Scenario: Duplicate name on one holder is collapsed before Write

- **GIVEN** a parsed ARC whose Investigation has two Comments both named `note` with different values
- **WHEN** the Git store syncs that ARC
- **THEN** `ARC.Write` succeeds
- **AND** only the last `note` value remains on the Investigation
- **AND** a warning is logged for the duplicate Comment name

#### Scenario: Same name on Investigation and Study remains allowed

- **GIVEN** a parsed ARC with Investigation `Comment[RDI]` and Study `Comment[RDI]` with values that may differ
- **WHEN** the Git store syncs that ARC
- **THEN** both Comments remain
- **AND** `ARC.Write` succeeds

#### Scenario: Person and Publication holders are covered

- **GIVEN** a parsed ARC where a Person and a Publication each have two Comments with the same name on that holder
- **WHEN** the Git store syncs that ARC
- **THEN** each holder retains a single Comment for that name (last-wins)
- **AND** `ARC.Write` succeeds
