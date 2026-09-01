## ADDED Requirements

### Requirement: Relativize catalog Dataset IDs after JSON-LD compact

When the consolidated backend JSON-LD-expands and compacts a catalog Dataset
on worker finalize, the published Dataset MUST use relative identifiers for
values that were relative in the source ARC (including root `./`, fragment IDs
such as `#Person_…` / `#LICENSE`, and path IDs such as `assays/<id>/` and
`studies/<id>/`). The published Dataset MUST NOT contain the JSON-LD processor
dummy base `http://example.org/base/` (or any path under that origin) in
identifier-bearing fields, including `@id`, `id`, `license`, and nested
`@id` values (for example `creator`, `hasPart`, `comment`, `citation`).
Canonical Dataset identity for catalog consumers remains the Dataset
`identifier` property. Expand/compact MUST still run; this requirement does not
replace schema.org compact.

#### Scenario: ARCtrl root Dataset keeps relative root id

- **GIVEN** a Dataset extracted from an ARCtrl-style RO-Crate whose root `@id`
  is `./` and whose `identifier` is a non-empty string
- **WHEN** worker finalize expands and compacts that Dataset for the catalog
- **THEN** the published Dataset `@id` (and `id` if present) equals `./`
- **AND** the value does not contain `http://example.org/base/`

#### Scenario: Fragment and path IDs stay relative

- **GIVEN** a Dataset whose nested nodes use relative `@id` values such as
  `#Person_1`, `#LICENSE`, and `assays/assay-a/`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** those `@id` values in the published Dataset remain relative (same
  relative form as the source, without `http://example.org/base/`)

#### Scenario: Absolute IRIs that were already absolute stay absolute

- **GIVEN** a Dataset field whose `@id` or IRI value is already an absolute
  HTTP(S) URL other than the dummy compact base
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** that absolute IRI remains absolute and is not rewritten to a
  relative form

#### Scenario: identifier and schema.org compact are preserved

- **GIVEN** an ARCtrl-style Dataset with `identifier` and schema.org properties
  such as `name`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** `identifier` equals the source value
- **AND** schema.org properties remain short names as required by catalog compact

### Requirement: Do not emit compact @base in public catalog context

The `@context` written into each published catalog Dataset MUST remain
`["https://schema.org", <ARC/Bioschemas extension map>]`. It MUST NOT include
`@base` and MUST NOT include `http://example.org/base/` or `example.org`.

#### Scenario: Public context has no @base

- **GIVEN** a Dataset compacted for catalog publish
- **WHEN** the Dataset is written into `{rdi}.json`
- **THEN** its `@context` is the schema.org IRI plus the ARC/Bioschemas
  extension map
- **AND** `@context` does not contain `@base`
- **AND** `@context` does not contain `example.org`
