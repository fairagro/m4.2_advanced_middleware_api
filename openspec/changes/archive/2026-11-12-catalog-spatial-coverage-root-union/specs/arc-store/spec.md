## ADDED Requirements

### Requirement: Derive root spatialCoverage from Study Bounding Box parameters

When worker finalize materializes a catalog Dataset and root `spatialCoverage` is absent, it SHALL collect
ParameterValues named `Bounding Box` (case-insensitive) reachable from root `hasPart` Studies via `about` → `LabProcess`
→ `parameterValue`, parse usable `value`s, and set `spatialCoverage` to one `Place` → `GeoShape.box` for the
axis-aligned union (schema.org: south west north east, space-separated). Skip invalid/empty values; do not invent
coverage; do not mutate CouchDB ARC bodies.

#### Scenario: Union of Study Bounding Box parameters becomes spatialCoverage

- **GIVEN** a root Dataset without `spatialCoverage` whose `hasPart` Studies reach LabProcess ParameterValues named
  `Bounding Box` with parseable values that cover `48 8 49 9` and `48.5 8.5 50 10`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset `spatialCoverage` is a `Place` with `geo` `GeoShape.box` equal to the union envelope
  `48 8 50 10`

#### Scenario: No parseable Bounding Box leaves spatialCoverage unset

- **GIVEN** a root Dataset without `spatialCoverage` and no reachable parseable `Bounding Box` ParameterValues
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset has no `spatialCoverage` property invented by materialize

### Requirement: Preserve existing spatialCoverage and Study hasPart shape for Bounding Box derivation

When deriving Bounding Box coverage, finalize MUST NOT overwrite an existing root `spatialCoverage` and MUST NOT add
`spatialCoverage` to catalog `hasPart` Study/Assay objects solely from this derivation.

#### Scenario: Existing spatialCoverage is not overwritten

- **GIVEN** a root Dataset that already has `spatialCoverage` and reachable `Bounding Box` ParameterValues
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset `spatialCoverage` is unchanged

#### Scenario: hasPart Studies do not gain spatialCoverage from this derivation

- **GIVEN** a root Dataset with reachable `Bounding Box` ParameterValues and a `hasPart` Study reference
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published root may have derived `spatialCoverage`
- **AND** the inline `hasPart` Study object does not include a `spatialCoverage` property solely from this derivation

## MODIFIED Requirements

### Requirement: Do not materialize non-catalog RO-Crate subgraphs

Materialization MUST NOT copy the full RO-Crate `@graph` or **emit** `LabProcess`, `Sample`, `PropertyValue`, `File`,
`LabProtocol`, or process/protocol subgraphs into the published catalog Dataset. Finalize MAY **read** `LabProcess` /
ParameterValue (`PropertyValue`) nodes solely to derive root `spatialCoverage` under the Bounding Box requirement; those
nodes MUST NOT appear in the published Dataset or its `hasPart` tree.

#### Scenario: LabProcess nodes stay out of catalog

- **GIVEN** a Study `Dataset` whose `about` references `LabProcess` nodes
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Study `hasPart` or inline Study object does not include those `LabProcess` nodes

#### Scenario: ParameterValue read for Bounding Box does not emit PropertyValue

- **GIVEN** LabProcess ParameterValues named `Bounding Box` used to derive root `spatialCoverage`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset does not contain those ParameterValue / PropertyValue nodes as nested objects
