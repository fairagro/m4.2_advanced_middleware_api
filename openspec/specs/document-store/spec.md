# Document Store (CouchDB)

## Purpose

The document store is the single CouchDB persistence layer for ARC documents, harvest documents, and optional task
records. These document types share one database and are isolated by key prefix.

## Requirements

### Requirement: Initialize CouchDB safely

On initialization, the store SHALL ensure the application database and CouchDB `_users`, `_replicator`, and
`_global_changes` system databases exist. It MUST treat `412 Precondition Failed` during creation as success so parallel
service startup does not crash.

#### Scenario: Start services concurrently

- **GIVEN** two containers initialize against an absent database
- **WHEN** both attempt creation
- **THEN** a `412 Precondition Failed` is handled as successful initialization

### Requirement: Store ARC documents idempotently

The store SHALL key ARC documents by `arc_id`, derived with `calculate_arc_id` from the RO-Crate root `identifier` and
`rdi`, and SHALL return whether the document was created and whether content changed according to its hash. An identical
existing ARC MUST avoid a body write, though timestamp fields MAY be updated.

#### Scenario: Re-submit identical ARC content

- **GIVEN** an ARC document with the same content hash
- **WHEN** it is stored again
- **THEN** the content-changed flag is false and no body write occurs

### Requirement: Preserve harvest-local ARC identity

When `harvest_id` is present and the same `arc_id` already has that `last_harvest_id`, matching content SHALL follow the
unchanged path without a second document. A differing hash MUST raise `DuplicateArcError` and leave the existing
document body and hash unchanged.

#### Scenario: Re-submit identical content in a harvest

- **GIVEN** the same ARC already recorded for a harvest
- **WHEN** its matching content is stored
- **THEN** the store reports unchanged and does not raise `DuplicateArcError`

#### Scenario: Re-submit conflicting content in a harvest

- **GIVEN** the same ARC already recorded for a harvest
- **WHEN** different content is stored
- **THEN** `DuplicateArcError` is raised and stored content is unchanged

### Requirement: Resolve concurrent document revisions

For concurrent writes, the store SHALL remove stale `_rev`, refetch the latest revision on each attempt, and retry
`ConflictError` up to the configured maximum (default 3). Each retry MUST apply the same harvest hash rules; after
exhaustion it MUST raise `DocumentConflictError`.

#### Scenario: Race with identical ARC content

- **GIVEN** concurrent workers write the same ARC
- **WHEN** a revision conflict occurs
- **THEN** retry uses the current revision and resolves identical harvest content as unchanged

### Requirement: Manage harvest data, events, and resources

The store SHALL create, retrieve, calculate statistics for, and update harvest documents, including terminal
transitions. It MUST append ARC event records and release its HTTP session and database client at shutdown. An unknown
harvest lookup SHALL return nothing so callers can raise `ResourceNotFoundError`.

#### Scenario: Shut down the store

- **GIVEN** a connected document store
- **WHEN** it shuts down
- **THEN** the underlying HTTP session and database client are released
