# Spec Delta

## MODIFIED Requirements

### Requirement: Support optional finalize on ArcStore

The `ArcStore` port SHALL expose a `finalize` operation scoped to an RDI (`finalize(rdi=…)`). The per-ARC `GitRepo`
backend MUST implement `finalize` as a successful no-op. Callers MUST be able to invoke `finalize` after a harvest
without branching on backend type. Finalize MUST NOT take `harvest_id` as a store argument (CouchDB holds latest ARC
bodies only; harvest cannot filter catalog membership).

#### Scenario: Finalize on per-ARC Git backend

- **GIVEN** `git_repo` is the configured per-ARC store
- **WHEN** `finalize` is invoked for an RDI
- **THEN** the call succeeds without writing a consolidated catalog file

### Requirement: Dual ArcStore configuration slots

Configuration MUST provide a **required** `arc_store` slot for per-ARC Git persistence and MAY provide an **optional**
`consolidated_store` slot for the shared RDI catalog. The `arc_store` backend MUST be configured via nested `git_repo`
settings (exactly that key). There MUST NOT be a separate `type` discriminator field on either slot. The
`consolidated_store` slot MUST configure consolidated catalog settings under `consolidated_git` (slot name selects the
catalog role). Putting catalog settings under `arc_store` MUST fail validation. Nested `gitlab_api` under `arc_store`
MUST fail validation. Top-level `git_repo`, `gitlab_api`, and `consolidated_git` MUST NOT be model fields (they are not
accepted as configuration). Config that relies only on those keys MUST fail on the API config model (required
`arc_store` missing and/or unknown top-level fields forbidden). The API `Config` model MUST reject unknown top-level
fields (`extra="forbid"`). The worker `WorkerConfig` projection MUST ignore API-only keys from the same shared flat file
(it is not a second full schema). Each slot MAY carry its own `git` CLI settings object using the shared Git CLI
settings type.

#### Scenario: Accept GitRepo plus optional catalog

- **GIVEN** `arc_store.git_repo` is set with nested settings and `consolidated_store` is set
- **WHEN** configuration is validated
- **THEN** validation succeeds and both slots are available to the runtime

#### Scenario: Reject catalog settings under arc_store

- **GIVEN** `arc_store` contains only `consolidated_git` (no `git_repo`)
- **WHEN** configuration is validated
- **THEN** validation fails before the API or worker starts

#### Scenario: Reject nested gitlab_api under arc_store

- **GIVEN** `arc_store` contains nested `gitlab_api` (with or without `git_repo`)
- **WHEN** configuration is validated
- **THEN** validation fails before the API or worker starts

#### Scenario: Obsolete top-level store keys are not configuration

- **GIVEN** only a top-level `git_repo`, `gitlab_api`, or `consolidated_git` key is provided (no `arc_store`)
- **WHEN** configuration is validated
- **THEN** validation fails (unknown top-level fields and/or missing required `arc_store`)

#### Scenario: Reject unknown top-level fields alongside dual slots

- **GIVEN** API `Config` validation with `arc_store` configured and an unknown top-level field also present
- **WHEN** configuration is validated
- **THEN** validation fails before the API starts

#### Scenario: Worker projection ignores API-only keys

- **GIVEN** the shared flat config includes API-only fields such as `client_auth_oid` plus a valid `arc_store`
- **WHEN** `WorkerConfig` is validated
- **THEN** validation succeeds and API-only fields are ignored
