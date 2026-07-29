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
