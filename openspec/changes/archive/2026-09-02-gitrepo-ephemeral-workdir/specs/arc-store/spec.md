# ARC Store — Delta

## ADDED Requirements

### Requirement: Use unique ephemeral local Git working directories for GitRepo

For the per-ARC Git CLI backend, each create-or-update or get operation that uses a
local clone SHALL allocate a working directory under the configured cache directory
that is unique to that invocation. The store MUST NOT reuse a fixed path keyed only
by `arc_id` for concurrent local clones. After the operation completes or fails, the
store MUST remove that working directory. The remote repository identity remains
`arc_id`; only the local path is ephemeral.

#### Scenario: Concurrent syncs for the same ARC

- **GIVEN** two overlapping create-or-update operations for the same `arc_id` on one
  host
- **WHEN** each allocates a local Git working directory
- **THEN** the two working directory paths are distinct
- **AND** neither operation deletes or overwrites the other's working tree

#### Scenario: Cleanup after sync

- **GIVEN** a create-or-update that finished (success or failure)
- **WHEN** the operation returns
- **THEN** that invocation's working directory no longer exists under the cache
  directory

### Requirement: Reclaim stale ephemeral Git cache directories

The Git CLI backends that place ephemeral clones under the shared cache directory
SHALL best-effort remove orphan directories left by crashed or interrupted operations.
Cleanup MUST only target known ephemeral name patterns (and legacy per-`arc_id`
directories from prior deployments) that are older than a configured age threshold.
Cleanup MUST NOT remove directories that are younger than that threshold or that do
not match those patterns.

#### Scenario: Stale orphan is removed

- **GIVEN** a cache directory containing an orphan ephemeral working directory older
  than the age threshold
- **WHEN** reclaim runs
- **THEN** that directory is deleted

#### Scenario: Active or recent workdir is preserved

- **GIVEN** a cache directory containing an ephemeral working directory younger than
  the age threshold
- **WHEN** reclaim runs
- **THEN** that directory remains
