## ADDED Requirements

### Requirement: Dual ArcStore configuration slots

Configuration MUST provide a **required** `arc_store` slot for per-ARC Git persistence and MAY provide an **optional**
`consolidated_store` slot for the shared RDI catalog. The `arc_store` slot MUST accept only `git_repo` or deprecated
`gitlab_api` (discriminator `type`). The `consolidated_store` slot MUST configure consolidated catalog settings only;
its `type` MAY be omitted and MUST be treated as consolidated catalog when present. Configuring `arc_store.type` as
`consolidated_git` MUST fail validation. Top-level `git_repo`, `gitlab_api`, and `consolidated_git` keys MUST NOT be
accepted. Each slot MAY carry its own `git` CLI settings object using the shared Git CLI settings type.

#### Scenario: Accept GitRepo plus optional catalog

- **GIVEN** `arc_store.type` is `git_repo` with nested settings and `consolidated_store` is set
- **WHEN** configuration is validated
- **THEN** validation succeeds and both slots are available to the runtime

#### Scenario: Reject consolidated type under arc_store

- **GIVEN** `arc_store.type` is `consolidated_git`
- **WHEN** configuration is validated
- **THEN** validation fails before the API or worker starts

#### Scenario: Reject obsolete top-level store keys

- **GIVEN** a top-level `git_repo`, `gitlab_api`, or `consolidated_git` key is present
- **WHEN** configuration is validated
- **THEN** validation fails

### Requirement: Role-based ArcStore operations

The per-ARC `arc_store` MUST perform per-ARC `create_or_update` (Git sync). The optional `consolidated_store`, when
configured, MUST perform RDI `finalize` for catalog publish. The system MUST NOT invoke catalog `finalize` on the
per-ARC store as the catalog implementation, and MUST NOT invoke per-ARC `create_or_update` on the consolidated store
for sync. When `consolidated_store` is absent, the system MUST NOT enqueue catalog finalize. There is **no** cross-store
ordering guarantee between per-ARC sync completion and catalog finalize; catalog rebuild MUST use document-store ARC
bodies for the RDI.

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

### Requirement: Dual-slot Git backend health checks

When global Git-backend health checks are enabled, the system MUST include a check for the required `arc_store`. When
`consolidated_store` is also configured, the system MUST include a separate check for that store. There MUST NOT be a
separate feature flag solely to disable the consolidated health check. Aggregate global health status MUST fail when any
included check is false (same aggregation as other health services).

#### Scenario: Both backends appear when consol. configured

- **GIVEN** git-backend global health is enabled and both slots are configured
- **WHEN** `/v3/health` runs
- **THEN** the response includes distinct checks for `arc_store` and `consolidated_store`
- **AND** if either is false, overall health is ERROR

## REMOVED Requirements

### Requirement: Select exactly one ArcStore backend

**Reason:** Dual-slot product need (#517); catalog complements per-ARC Git instead of replacing it.

**Migration:** Use required `arc_store` (`git_repo` | deprecated `gitlab_api`) plus optional `consolidated_store`.
Remove top-level store keys. Replace any `arc_store.type: consolidated_git` with `consolidated_store` plus a real
per-ARC `arc_store`.
