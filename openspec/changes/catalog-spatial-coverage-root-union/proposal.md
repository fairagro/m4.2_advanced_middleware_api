# Proposal

## Why

Search Hub needs geographic coverage on basic-layout dumps (`spatialCoverage[].geo.box`). INSPIRE boxes already live in
the ARC as Study **AnnotationTable / ParameterValue** entries named `Bounding Box`, but the Investigation-rooted catalog
never derives a root coverage from them. Product lock-in (#553): expose **one** root `spatialCoverage` whose box is the
**axis-aligned union** of those Study boxes, **without changing the stored ARC**. Per-Study dump fields stay in
Discussion #684.

## What Changes

- During worker catalog materialize only, **read** Study-linked `Bounding Box` ParameterValue nodes from the source
  RO-Crate `@graph`, compute an axis-aligned WGS84 union envelope, and set root Dataset `spatialCoverage` to `Place` →
  `GeoShape.box` when `spatialCoverage` is absent and at least one parseable box exists.
- Do **not** mutate CouchDB ARC bodies or per-ARC Git content; do **not** invent coverage when no parseable Study boxes
  exist; do **not** overwrite an existing root `spatialCoverage`.
- Do **not** publish `spatialCoverage` on catalog `hasPart` Study objects in this change (allowlist unchanged).
- Do **not** introduce an Investigation Comment (or other ARC write) as the transport for the union.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Require deriving root Dataset `spatialCoverage` from Study `Bounding Box` ParameterValues on materialize
  (union envelope; ARC unchanged).

## Impact

- Code: `catalog_materialize.py` (read-only `@graph` scan + union + root field) and unit tests.
- Specs: `openspec/specs/arc-store/` (materialize requirement; clarify read-only ParameterValue scan vs “do not emit
  LabProcess/PropertyValue subgraphs”).
- Harvester: no new Comment required for #553 if Study `Bounding Box` parameters are already written; ensure string
  formats are parseable (existing INSPIRE mapper). Tracking Task #685 should be closed or retargeted.
- Search Hub: continues to read root `spatialCoverage[0].geo.box`.
- Out of scope: per-Study `spatialCoverage` on `hasPart` (#684); inventing boxes; rewriting ARC Comments/tables.
