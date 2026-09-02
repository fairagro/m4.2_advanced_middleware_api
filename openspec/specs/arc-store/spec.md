# ARC Store

## Purpose

`ArcStore` is the Git-backend persistence abstraction for parsed ARC objects. It creates or updates their repositories
without depending on Celery, CouchDB, or HTTP; its caller, described in `arc-manager/`, owns parsing, events, and retry
policy.

## Requirements

### Requirement: Persist parsed ARCs to stable Git repositories

The store SHALL accept a parsed ARC and unique ARC identifier, create its repository when absent, and update it
otherwise. It MUST support arbitrary Git servers and keep the repository path or slug equal to `arc_id`.

#### Scenario: Create or update by ARC ID

- **GIVEN** a parsed ARC and `arc_id`
- **WHEN** the store syncs it
- **THEN** it creates or updates the repository whose stable path is that `arc_id`

### Requirement: Classify Git persistence failures

The store SHALL raise a retryable error for transient network timeouts, rate limits, or temporary backend
unavailability. It MUST raise a permanent error for invalid credentials, missing permissions, corrupt ARC data, or a
missing or malformed ARC identifier before performing Git operations.

#### Scenario: Encounter a transient backend failure

- **GIVEN** a temporary network or availability failure
- **WHEN** sync occurs
- **THEN** the store raises a retryable error for the caller

#### Scenario: Encounter an invalid ARC identifier

- **GIVEN** a missing or malformed ARC identifier
- **WHEN** sync is attempted
- **THEN** a permanent error is raised before Git activity

### Requirement: Populate GitLab project metadata

For `GitRepo` with GitLab, the store SHALL set project title to `{sanitized Identifier} - {rdi}`, keep path as `arc_id`,
and derive description from the root RO-Crate `name` and `description`. It MUST NOT duplicate identifier, RDI, or
`arc_id` in the description; it MUST truncate the combined description to 2000 characters.

#### Scenario: Sync without a RO-Crate name

- **GIVEN** a root dataset without `name`
- **WHEN** GitLab metadata is built
- **THEN** `display_name=""` is passed and the description may still contain the RO-Crate description

#### Scenario: Sync a long RO-Crate summary

- **GIVEN** name and description together exceed 2000 characters
- **WHEN** GitLab metadata is built
- **THEN** the description is truncated to 2000 characters and sync does not fail for length

### Requirement: Maintain one RDI GitLab topic

For `GitRepo` with GitLab, the store SHALL set exactly one project topic derived from the originating RDI. It MUST use
`git_repo.rdi_gitlab_topics` when the instance label differs; when `known_rdis` is non-empty, that mapping MUST provide
exactly one non-empty entry per known RDI. Each sync MUST replace the project topic list with that one resolved topic.

#### Scenario: Map an instance-specific topic

- **GIVEN** the RDI `edal` maps to `e!DAL`
- **WHEN** the project is synced
- **THEN** GitLab receives `e!DAL` as its only RDI topic

### Requirement: Refresh existing GitLab metadata

When a GitLab project already exists for an `arc_id`, `GitRepo` SHALL update its title, description, and RDI topic on
the next sync whenever current values differ. API validation MUST reject unknown or disallowed RDIs before the Git store
receives them, as specified in `arc-upload/` and `harvest-arc-upload/`.

#### Scenario: Re-sync an old project

- **GIVEN** an existing project has outdated display metadata
- **WHEN** its ARC is synced
- **THEN** the changed title, description, and single topic are persisted

### Requirement: Relativize catalog Dataset IDs after JSON-LD compact

When the consolidated backend JSON-LD-expands and compacts a catalog Dataset
on worker finalize, the published Dataset MUST use relative identifiers for
values that were relative in the source ARC (including root `./`, fragment IDs
such as `#Person_…` / `#LICENSE`, and path IDs such as `assays/<id>/` and
`studies/<id>/`). The published Dataset MUST NOT contain the JSON-LD processor
dummy base `http://example.org/base/` (or any path under that origin) in
identifier-bearing fields, including `@id`, `id`, `license`, and nested
`@id` values (for example `creator`, `hasPart`, `comment`, `citation`).
Canonical Dataset identity for catalog consumers remains the Dataset
`identifier` property. Expand/compact MUST still run; this requirement does not
replace schema.org compact.

#### Scenario: ARCtrl root Dataset keeps relative root id

- **GIVEN** a Dataset extracted from an ARCtrl-style RO-Crate whose root `@id`
  is `./` and whose `identifier` is a non-empty string
- **WHEN** worker finalize expands and compacts that Dataset for the catalog
- **THEN** the published Dataset `@id` (and `id` if present) equals `./`
- **AND** the value does not contain `http://example.org/base/`

#### Scenario: Fragment and path IDs stay relative

- **GIVEN** a Dataset whose nested nodes use relative `@id` values such as
  `#Person_1`, `#LICENSE`, and `assays/assay-a/`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** those `@id` values in the published Dataset remain relative (same
  relative form as the source, without `http://example.org/base/`)

#### Scenario: Absolute IRIs that were already absolute stay absolute

- **GIVEN** a Dataset field whose `@id` or IRI value is already an absolute
  HTTP(S) URL other than the dummy compact base
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** that absolute IRI remains absolute and is not rewritten to a
  relative form

#### Scenario: identifier and schema.org compact are preserved

- **GIVEN** an ARCtrl-style Dataset with `identifier` and schema.org properties
  such as `name`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** `identifier` equals the source value
- **AND** schema.org properties remain short names as required by catalog compact

### Requirement: Do not emit compact @base in public catalog context

The `@context` written into each published catalog Dataset MUST remain
`["https://schema.org", <ARC/Bioschemas extension map>]`. It MUST NOT include
`@base` and MUST NOT include `http://example.org/base/` or `example.org`.

#### Scenario: Public context has no @base

- **GIVEN** a Dataset compacted for catalog publish
- **WHEN** the Dataset is written into `{rdi}.json`
- **THEN** its `@context` is the schema.org IRI plus the ARC/Bioschemas
  extension map
- **AND** `@context` does not contain `@base`
- **AND** `@context` does not contain `example.org`

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
