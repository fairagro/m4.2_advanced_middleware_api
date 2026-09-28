## ADDED Requirements

### Requirement: ArcManager dual store references

`ArcManager` MUST hold a required per-ARC store reference and an optional consolidated catalog store reference.
Standalone and harvest-scoped ingestion MUST schedule per-ARC Git sync against the per-ARC store. Catalog finalize and
harvest `CATALOG_PUSH_*` recording MUST use the consolidated store only when it is configured. The manager MUST NOT
reject standalone ingestion based on a standalone-support flag on the store.

#### Scenario: Standalone ingestion always reaches sync scheduling

- **GIVEN** API mode with required `arc_store` configured
- **WHEN** standalone `create_or_update_arc` runs without a harvest id
- **THEN** content is staged in the document store when otherwise valid
- **AND** per-ARC Git sync is scheduled against `arc_store`
- **AND** no `InvalidRequestError` is raised for unsupported standalone upload

#### Scenario: Catalog events only with consolidated_store

- **GIVEN** `consolidated_store` is absent
- **WHEN** harvest completion would previously have recorded catalog push events
- **THEN** no `CATALOG_PUSH_*` events are appended for catalog finalize
