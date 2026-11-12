# Tasks

## 1. Derive root spatialCoverage from Study Bounding Box parameters

- [ ] 1.1 In `catalog_materialize.py`, after person/comment/hasPart wiring (or equivalent finalize order), discover
      `Bounding Box` ParameterValues reachable from root `hasPart` Studies (`about` → LabProcess → `parameterValue`),
      parse values, compute axis-aligned union, set root `spatialCoverage` Place/GeoShape.box when absent; never mutate
      ARC inputs; never emit LabProcess/PropertyValue into the published record — verify with 1.2
- [ ] 1.2 Add unit tests with synthetic `@graph` fixtures (multi-Study union; no boxes; invalid skipped; existing
      `spatialCoverage` preserved; compact short names; `hasPart` Study has no `spatialCoverage`; PropertyValue nodes
      absent from published JSON) — `uv run pytest middleware/api/tests/unit/test_catalog_materialize.py -k spatial -v`

## Workflow follow-up

- After implement + draft PR merge: `/opsx-archive` for `catalog-spatial-coverage-root-union`
- Close or retarget #685 (Comment transport abandoned)
- Future per-Study dump coverage: Discussion #684
