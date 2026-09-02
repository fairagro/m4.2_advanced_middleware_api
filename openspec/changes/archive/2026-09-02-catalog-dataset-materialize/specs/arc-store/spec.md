# ARC Store — Delta

## ADDED Requirements

### Requirement: Materialize referenced entities before catalog JSON-LD normalize

When the consolidated backend rebuilds an RDI catalog during **finalize**
(Celery worker), each extracted root `Dataset` SHALL be enriched from the
source RO-Crate `@graph` so dangling `@id` references become inline objects
**before** JSON-LD expand/compact. Materialization MUST run only on the worker
finalize path and MUST NOT mutate CouchDB ARC bodies or run on API ingest.

The catalog file MUST remain a JSON array of independent `Dataset` records (no
shared top-level `@graph` across all ARCs in `{rdi}.json`).

#### Scenario: Person reference becomes inline creator

- **GIVEN** a root `Dataset` whose `creator` is `{"@id": "#Person_Kevin_Urbasch"}`
  and the RO-Crate `@graph` contains a `Person` node with that `@id` and
  `givenName` / `familyName`
- **WHEN** worker finalize builds the catalog entry for that ARC
- **THEN** the published `creator` includes `givenName` and `familyName`
- **AND** the published `creator` is not solely a fragment `@id` reference

#### Scenario: Author and contributor use the same Person rules

- **GIVEN** a root `Dataset` with `author` or `contributor` referencing a
  `Person` node in `@graph`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published property contains the same inline Person fields as
  `creator`

#### Scenario: LDComment maps to schema.org where possible

- **GIVEN** a root `Dataset` whose `comment` references a `Comment` node with
  `name` matching a known metadata key (for example Keywords or Language) and
  `text` carrying the value
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the catalog entry uses the corresponding first-class schema.org
  property (for example `keywords` or `inLanguage`) when mappable
- **AND** only uses inline `Comment` with `name` and `text` when no mapping
  applies

#### Scenario: License placeholder resolves to text or URL

- **GIVEN** a root `Dataset` whose `license` is `{"@id": "#LICENSE"}` and the
  `@graph` contains a `#LICENSE` node with `url`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `license` is that URL string
- **AND** does not remain `#LICENSE`

#### Scenario: License placeholder with text only

- **GIVEN** a root `Dataset` whose `license` is `{"@id": "#LICENSE"}` and the
  `@graph` `#LICENSE` node has `text` but no `url`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `license` is the license text string
- **AND** does not remain `#LICENSE`

#### Scenario: hasPart includes nested Study and Assay Datasets

- **GIVEN** a root `Dataset` whose `hasPart` references `studies/…/` and
  `assays/…/` `Dataset` nodes in `@graph` with `name`, `identifier`, and
  `additionalType` of `Study` or `Assay`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** each published `hasPart` entry is an inline `Dataset` object with
  those fields
- **AND** a Study entry MAY include nested inline Assay `Dataset` objects in
  its own `hasPart` when referenced in `@graph`

#### Scenario: Citation materializes as ScholarlyArticle without Comment chain

- **GIVEN** a root `Dataset` whose `citation` references a `ScholarlyArticle`
  (or compatible `CreativeWork`) node with `headline` and/or `identifier`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `citation` is an inline object with those fields
- **AND** nested `comment` or status references on the publication node are
  not materialized into the catalog entry

#### Scenario: Missing reference target is omitted

- **GIVEN** a root `Dataset` property referencing an `@id` absent from `@graph`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** that list entry or property value is omitted from the published
  Dataset
- **AND** finalize continues for other ARCs (best-effort materialize)

### Requirement: Do not materialize non-catalog RO-Crate subgraphs

Materialization MUST NOT copy the full RO-Crate `@graph` or follow references
into `LabProcess`, `Sample`, `PropertyValue`, `File`, `LabProtocol`, or
process/protocol subgraphs (for example via `about` on Study nodes). Only the
properties and node types listed in the materialize requirement above SHALL be
followed.

#### Scenario: LabProcess nodes stay out of catalog

- **GIVEN** a Study `Dataset` whose `about` references `LabProcess` nodes
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Study `hasPart` or inline Study object does not
  include those `LabProcess` nodes

## MODIFIED Requirements

### Requirement: Relativize catalog Dataset IDs after JSON-LD compact

When the consolidated backend JSON-LD-expands and compacts a catalog Dataset
on worker finalize, the published Dataset MUST use relative identifiers for
**path-based** values that were relative in the source ARC (root `./`, and
path IDs such as `assays/<id>/` and `studies/<id>/` on `hasPart` children).
Inlined Person and Comment objects materialized for catalog export MUST NOT
retain fragment `@id` values (for example `#Person_…` or `#LDComment_…`); they
SHALL appear as anonymous inline nodes with `@type` and data properties only.
The published Dataset MUST NOT contain the JSON-LD processor dummy base
`http://example.org/base/` (or any path under that origin) in identifier-bearing
fields. Canonical Dataset identity for catalog consumers remains the Dataset
`identifier` property. Expand/compact MUST still run after materialization.

#### Scenario: ARCtrl root Dataset keeps relative root id

- **GIVEN** a Dataset extracted from an ARCtrl-style RO-Crate whose root `@id`
  is `./` and whose `identifier` is a non-empty string
- **WHEN** worker finalize materializes, expands, and compacts that Dataset for
  the catalog
- **THEN** the published Dataset `@id` (and `id` if present) equals `./`
- **AND** the value does not contain `http://example.org/base/`

#### Scenario: Path IDs on hasPart stay relative

- **GIVEN** a materialized `hasPart` child whose source `@id` is a relative
  path such as `studies/AthalianaColdStress/` or `assays/Proteomics_MS/`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** that child's `@id` (or `id`) remains the same relative path
- **AND** does not contain `http://example.org/base/`

#### Scenario: Inlined Person has no fragment id

- **GIVEN** a materialized inline `creator` Person sourced from
  `#Person_Kevin_Urbasch`
- **WHEN** worker finalize expands and compacts the catalog Dataset
- **THEN** the published `creator` object includes `givenName` / `familyName`
- **AND** does not contain `@id` or `id` equal to `#Person_Kevin_Urbasch`

#### Scenario: Absolute IRIs that were already absolute stay absolute

- **GIVEN** a Dataset field whose value is already an absolute HTTP(S) URL
  other than the dummy compact base (for example `sameAs` or DOI)
- **WHEN** worker finalize materializes, expands, and compacts that Dataset
- **THEN** that absolute IRI remains absolute and is not rewritten to a
  relative form

#### Scenario: identifier and schema.org compact are preserved

- **GIVEN** an ARCtrl-style Dataset with `identifier` and schema.org properties
  such as `name`
- **WHEN** worker finalize materializes, expands, and compacts that Dataset
- **THEN** `identifier` equals the source value
- **AND** schema.org properties remain short names as required by catalog compact
