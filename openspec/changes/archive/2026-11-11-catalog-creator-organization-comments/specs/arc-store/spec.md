## ADDED Requirements

### Requirement: Materialize Creator Organization Comments as schema.org Organization creators

When worker finalize materializes a catalog Dataset, Comments named `Creator Organization` (case-insensitive) SHALL
become schema.org `Organization` objects on Dataset `creator` **alongside** any Person creators. Names come from Comment
`text` (`; `-segments and/or multiple nodes, encounter order). Mapped Comments MUST NOT remain opaque Dataset `comment`
entries. Each Organization MUST have `@type` `Organization` and `name`, omit fragment `@id`s, and follow `creator`
list/object normalization.

#### Scenario: Organization creators appear beside Person creators

- **GIVEN** a root Dataset with a Person `creator` reference and a `comment` referencing a Comment named
  `Creator Organization` whose text is an organisation label
- **WHEN** worker finalize materializes the catalog entry
- **THEN** published `creator` includes the inline Person **and** an `Organization` with that `name`
- **AND** the `Creator Organization` Comment is not retained as an opaque Dataset `comment` entry

#### Scenario: Organization-only creators when no Person exists

- **GIVEN** a root Dataset with no Person `creator` and a `Creator Organization` Comment
- **WHEN** worker finalize materializes the catalog entry
- **THEN** published `creator` includes the `Organization`

### Requirement: Pair Creator Organization URL Comments by parallel index

Comment nodes whose `name` matches `Creator Organization URL` (case-insensitive) SHALL supply URLs for the organisations
produced under the Creator Organization materialize requirement. URL texts MAY use `; ` segmentation. URLs pair with
organisation names by parallel index after flattening both lists in encounter order. Unpaired names still publish
without `url`; extra URLs are ignored. Mapped URL Comments MUST NOT remain as opaque Dataset `comment` entries.

#### Scenario: Semicolon-joined organisations and parallel URLs

- **GIVEN** Comment `Creator Organization` text `Org A; Org B` and Comment `Creator Organization URL` text
  `https://a.example; https://b.example`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** published `creator` includes two `Organization` objects with names `Org A` / `Org B` and matching `url`
  values

#### Scenario: URL optional per organisation

- **GIVEN** Comment `Creator Organization` text `Org A; Org B` and a single `Creator Organization URL` segment for
  `Org A` only
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the first Organization has `url` and the second Organization has `name` only
