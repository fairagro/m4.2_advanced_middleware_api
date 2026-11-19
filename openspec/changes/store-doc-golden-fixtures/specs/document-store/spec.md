# Spec Delta

## ADDED Requirements

### Requirement: Keep golden fixtures for allowlisted persisted document models

The product test suite MUST keep golden JSON fixtures for an allowlisted set of persisted document models used by the
document store. The MVP allowlist MUST include the harvest run document model and the ARC document model (persistence
envelope / metadata — not the public HTTP contract).

#### Scenario: Allowlist covers harvest and ARC

- **GIVEN** the golden-fixture suite is present in the repository
- **WHEN** the allowlist is inspected
- **THEN** it includes the harvest document model and the ARC document model

### Requirement: Tip models must validate every supported golden fixture

For every golden fixture marked as still **supported**, the tip revision of the corresponding model MUST successfully
validate that fixture. Failures MUST fail the test suite. Fixture failures MUST NOT be coupled to Conventional Commit
breaking markers or treated as a public API SemVer break.

#### Scenario: Supported older harvest fixture still validates

- **GIVEN** a golden fixture representing a supported older harvest document shape
- **WHEN** the tip harvest document model validates that fixture
- **THEN** validation succeeds

#### Scenario: Supported older ARC fixture still validates

- **GIVEN** a golden fixture representing a supported older ARC document shape
- **WHEN** the tip ARC document model validates that fixture
- **THEN** validation succeeds

#### Scenario: Incompatible tip model fails the suite

- **GIVEN** a tip model change that rejects a still-supported golden fixture (for example a new required field without
  default or backfill)
- **AND** that fixture remains in the supported set
- **WHEN** the golden-fixture tests run
- **THEN** the suite fails

### Requirement: Retire unsupported document-shape fixtures

When a document generation is no longer supported (migration complete and support window ended, or a cutover that
discards prior store data), its golden fixtures MUST be removed from the supported set (deleted or otherwise excluded
from validation). CouchDB-era fixtures that exist only to cover pre-cutover on-disk forms MUST be eligible for
retirement when the PostgreSQL document-store cutover without data migration is completed.

#### Scenario: Unsupported fixture is not required to validate

- **GIVEN** a document generation that the product no longer supports
- **AND** its golden fixture has been removed from the supported set
- **WHEN** the golden-fixture tests run
- **THEN** that fixture is not loaded and does not fail the suite
