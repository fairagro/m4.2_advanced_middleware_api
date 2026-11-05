# Spec Delta

## ADDED Requirements

### Requirement: Optional software version on the harvest-run report

The harvest-run report SHALL allow the caller to set an optional PEP 440 software version string (tool or image stamp)
on the mutable report. When unset (`None`), serializers MUST omit tool-version wire fields. Shared library finish and
render paths MUST NOT fail solely because the version is unset. Production harvest tools SHOULD set the version for
every productive run; fail-closed enforcement of that policy is outside this shared library.

#### Scenario: Version set by caller

- **GIVEN** a harvest-run report
- **WHEN** the caller sets a non-empty software version string
- **THEN** serializers that emit tool identity can read that string from the report

#### Scenario: Version unset remains valid

- **GIVEN** a harvest-run report with no software version set
- **WHEN** the caller finishes the run and renders JSON-LD
- **THEN** rendering succeeds
- **AND** the document does not include `schema:instrument`

### Requirement: Read installed distribution version for callers

The shared library SHALL provide a helper that accepts a Python distribution name and returns its installed PEP 440
version string, or `None` when the distribution metadata is not available. The helper MUST NOT hard-code a product
package name.

#### Scenario: Installed distribution

- **GIVEN** a distribution name that is installed in the environment
- **WHEN** the helper is invoked with that name
- **THEN** it returns a non-empty version string

#### Scenario: Missing distribution

- **GIVEN** a distribution name that is not installed
- **WHEN** the helper is invoked with that name
- **THEN** it returns `None`

### Requirement: JSON-LD emits schema:instrument when version is set

When the finished report has a software version set, JSON-LD serialization SHALL include `schema:instrument` as an
object with `@type` `schema:SoftwareApplication` and `schema:softwareVersion` equal to that string. When unset,
`schema:instrument` MUST be omitted. This MUST NOT require a new harvest-report vocabulary major version (schema.org
terms only).

#### Scenario: Instrument present with version

- **GIVEN** a finished report with software version `1.2.3`
- **WHEN** JSON-LD is produced
- **THEN** `schema:instrument` has `@type` `schema:SoftwareApplication`
- **AND** `schema:softwareVersion` is `1.2.3`

#### Scenario: Instrument omitted without version

- **GIVEN** a finished report with software version unset
- **WHEN** JSON-LD is produced
- **THEN** the document has no `schema:instrument` property
