## ADDED Requirements

### Requirement: Materialize Landing Page Comment as Dataset url

When worker finalize materializes a catalog Dataset, Comments named `Landing Page` (case-insensitive) SHALL set Dataset
`url` to `{"@id": "<text>"}` when `url` is absent and `text` is non-empty, MUST NOT overwrite an existing `url`, MUST
consume the Comment from opaque `comment` entries, and MUST NOT invent `url` without that Comment. ARC bodies stay
unchanged.

#### Scenario: Landing Page Comment becomes Dataset url

- **GIVEN** a root Dataset without `url` whose `comment` references a Comment named `Landing Page` with non-empty `text`
  `https://example.org/landing`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset has `url` as `{"@id": "https://example.org/landing"}` before compact (and the `url`
  term after compact)
- **AND** the `Landing Page` Comment is not retained as an opaque Dataset `comment` entry

#### Scenario: Existing url is not overwritten

- **GIVEN** a root Dataset that already has `url` and a `Landing Page` Comment with different `text`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset `url` is unchanged
- **AND** the `Landing Page` Comment is not retained as an opaque Dataset `comment` entry

#### Scenario: No Landing Page Comment leaves url unset

- **GIVEN** a root Dataset without `url` and without a `Landing Page` Comment
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset has no `url` property invented by materialize
