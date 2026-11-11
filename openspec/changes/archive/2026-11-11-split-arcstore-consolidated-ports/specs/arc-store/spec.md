## ADDED Requirements

### Requirement: Distinct ArcStore and ConsolidatedArcStore ports

The system MUST expose two role ports that share only lifecycle (health and shutdown). The per-ARC port MUST provide
sync ops (`create_or_update` and any get/delete/exists surface). The catalog port MUST provide RDI `finalize` only.
Dual-slot wiring MUST type `arc_store` as the per-ARC port and `consolidated_store` as the catalog port or `None`.

#### Scenario: Factory types match dual slots

- **GIVEN** both slots are configured
- **WHEN** the runtime constructs ArcStore backends for the dual slots
- **THEN** the per-ARC slot instance is the per-ARC port type
- **AND** the consolidated slot instance is the catalog port type

#### Scenario: Catalog port has no per-ARC sync API

- **GIVEN** a configured consolidated catalog backend
- **WHEN** callers sync an ARC via the dual-slot runtime
- **THEN** only the per-ARC slot receives `create_or_update`
- **AND** the catalog port is not used as a per-ARC sync target

#### Scenario: Per-ARC port has no catalog finalize API

- **GIVEN** a configured per-ARC Git backend
- **WHEN** a harvest completes and catalog finalize is enqueued
- **THEN** only the consolidated slot receives `finalize`
- **AND** the per-ARC port is not invoked for catalog publish

### Requirement: Catalog finalize skip outcomes on ConsolidatedArcStore

When the consolidated catalog backend completes a successful `finalize` for an RDI (including when remote catalog bytes
are unchanged), the operation MUST return whether a push occurred, the included Dataset count, and each skipped ARC’s
`arc_id` with a human-readable reason. Permanent store errors (including all-ARC failure that refuses an empty wipe)
MUST remain exceptions and MUST NOT pretend success with an empty skip list.

#### Scenario: Successful partial finalize reports skips

- **GIVEN** a consolidated finalize that includes at least one Dataset and skips at least one ARC for extract or JSON-LD
  failure
- **WHEN** finalize completes without raising
- **THEN** the outcome indicates the included Dataset count and lists each skipped `arc_id` with a reason
- **AND** the push flag reflects whether remote bytes were updated

## MODIFIED Requirements

### Requirement: Role-based ArcStore operations

The per-ARC `arc_store` (typed as the per-ARC `ArcStore` port) MUST perform per-ARC `create_or_update` (Git sync). The
optional `consolidated_store` (typed as `ConsolidatedArcStore | None`), when configured, MUST perform RDI `finalize` for
catalog publish. The system MUST NOT invoke catalog `finalize` on the per-ARC store as the catalog implementation, and
MUST NOT invoke per-ARC `create_or_update` on the consolidated store for sync. When `consolidated_store` is absent, the
system MUST NOT enqueue catalog finalize. There is **no** cross-store ordering guarantee between per-ARC sync completion
and catalog finalize; catalog rebuild MUST use document-store ARC bodies for the RDI.

#### Scenario: Sync uses only arc_store

- **GIVEN** both slots are configured
- **WHEN** a worker runs per-ARC Git sync
- **THEN** only `arc_store` receives `create_or_update`
- **AND** `consolidated_store` is not called for that sync

#### Scenario: Finalize uses only consolidated_store

- **GIVEN** `consolidated_store` is configured
- **WHEN** a worker runs catalog finalize for an RDI
- **THEN** only `consolidated_store` receives `finalize`
- **AND** `arc_store` is not used as the catalog publisher

#### Scenario: No finalize enqueue without consolidated_store

- **GIVEN** only `arc_store` is configured
- **WHEN** a harvest transitions to `COMPLETED`
- **THEN** no catalog finalize task is enqueued

## REMOVED Requirements

### Requirement: Support optional finalize on ArcStore

**Reason:** Catalog finalize belongs only on the `ConsolidatedArcStore` port after the Split-ports refactor (#615 /
#518). A shared `ArcStore.finalize` (with per-ARC no-op) is leftover tax from the single-ABC era and contradicts
role-based dual-slot typing.

**Migration:** Callers MUST invoke `finalize` only on the optional `consolidated_store` (`ConsolidatedArcStore`).
Per-ARC backends MUST NOT implement or inherit catalog `finalize`. Orchestrators already branch on whether
`consolidated_store` is configured before enqueueing finalize.

### Requirement: Expose catalog finalize skip outcomes to callers

**Reason:** Replaced by “Catalog finalize skip outcomes on ConsolidatedArcStore”, which drops the obsolete scenario
requiring per-ARC backends to expose a no-op `finalize` outcome.

**Migration:** Use the ADDED requirement above; callers read skip outcomes only from consolidated `finalize`.
