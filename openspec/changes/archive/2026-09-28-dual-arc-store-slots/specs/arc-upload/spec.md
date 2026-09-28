## ADDED Requirements

### Requirement: Standalone upload uses per-ARC store only

Standalone ARC create endpoints (`POST /v1/arcs`, `POST /v2/arcs`, and `POST /v3/arcs`) MUST always be accepted when the
API is otherwise healthy. They MUST stage content and schedule per-ARC Git sync via the required `arc_store` slot. They
MUST NOT publish or finalize the consolidated RDI catalog. API models exposed in OpenAPI/Swagger MUST describe that
standalone uploads update the per-ARC store only and do not update the consolidated catalog.

#### Scenario: Standalone accepted with consolidated_store configured

- **GIVEN** both `arc_store` and `consolidated_store` are configured
- **WHEN** a client calls `POST /v3/arcs`
- **THEN** the API accepts the request (subject to normal validation)
- **AND** schedules per-ARC sync via `arc_store`
- **AND** does not enqueue catalog finalize for that request

## REMOVED Requirements

### Requirement: Reject standalone upload when consolidated Git store is configured

**Reason:** Dual-slot deployments always have a per-ARC `arc_store`; standalone gating via `supports_standalone_upload`
/ consolidated-as-sole-backend no longer applies (#517).

**Migration:** Use harvest-scoped upload when the consolidated catalog must be updated; standalone remains valid for
per-ARC Git only.
