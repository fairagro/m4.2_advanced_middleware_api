# Document Store (CouchDB)

## Purpose

The document store is the single CouchDB persistence layer for ARC documents, harvest documents, and optional task
records. These document types share one database and are isolated by key prefix.

## Requirements

### Requirement: Initialize CouchDB safely

On initialization, the store SHALL ensure the application database and CouchDB `_users`, `_replicator`, and
`_global_changes` system databases exist, and SHALL ensure the indices required for normal operation. It MUST treat
`412 Precondition Failed` during creation as success so parallel service startup does not crash. The same initialization
work MUST be safe to re-run after process start when the application database (or required system databases) is found
missing.

#### Scenario: Start services concurrently

- **GIVEN** two containers initialize against an absent database
- **WHEN** both attempt creation
- **THEN** a `412 Precondition Failed` is handled as successful initialization

#### Scenario: Re-initialize after application database disappears

- **GIVEN** a process that already completed initialization against CouchDB
- **AND** the application database (and possibly system databases) are later removed or CouchDB is recreated empty
- **WHEN** initialization is requested again
- **THEN** the application database, required system databases, and required indices are recreated without restarting
  the process

### Requirement: Recover from a wiped CouchDB without process restart

When a document-store operation fails because the application database no longer exists (while the process still holds a
prior connection), the store MUST attempt a guarded re-initialization (single-flight across concurrent callers) and MUST
retry the failed operation once after successful re-initialization. Concurrent callers during re-initialization MUST NOT
trigger uncontrolled parallel recreate storms or leave the store half-initialized. Document-not-found for a specific
document id MUST NOT be treated as a missing application database.

#### Scenario: Write after CouchDB wipe recovers

- **GIVEN** the API process completed startup initialization
- **AND** CouchDB is wiped so the application database is gone
- **WHEN** a document write (e.g. harvest create) is attempted
- **THEN** the store re-initializes and the write succeeds after re-initialization completes

#### Scenario: Concurrent requests share one re-initialization

- **GIVEN** the application database is missing
- **WHEN** several requests detect the missing database at the same time
- **THEN** only one re-initialization runs to completion for that failure window
- **AND** the others wait for that result rather than each creating databases independently without coordination

#### Scenario: Missing document is not a missing database

- **GIVEN** the application database exists
- **WHEN** a read or write targets a document id that does not exist
- **THEN** re-initialization is not triggered solely for that reason

### Requirement: Surface recoverable CouchDB unavailability as service unavailable

While re-initialization is in progress, or when re-initialization fails and the application database remains
unavailable, callers that need the document store MUST receive a service-unavailable outcome suitable for HTTP `503`
(with a clear indication that CouchDB initialization is incomplete or failed). A missing application database that can
still be recovered MUST NOT surface as an unhandled generic server error (`500`) when recovery was attempted or is in
progress.

#### Scenario: Request during re-initialization

- **GIVEN** re-initialization is running after a wiped CouchDB
- **WHEN** a document-store-dependent request cannot proceed yet
- **THEN** the outcome is service unavailable rather than an unhandled internal error

### Requirement: Readiness reflects application database presence

Health checks used for readiness that claim CouchDB readiness MUST verify that the configured application database
exists (not only that the CouchDB server process answers). If the application database is missing, readiness MUST fail
until successful re-initialization. The readiness path MAY trigger the same guarded re-initialization used by the write
path.

#### Scenario: Empty CouchDB fails readiness

- **GIVEN** CouchDB is reachable but the application database does not exist
- **WHEN** readiness is evaluated
- **THEN** readiness fails for the CouchDB dependency

#### Scenario: After re-initialization readiness passes

- **GIVEN** the application database was missing and has been successfully re-initialized
- **WHEN** readiness is evaluated
- **THEN** the CouchDB readiness check succeeds

### Requirement: Store ARC documents idempotently

The store SHALL key ARC documents by `arc_id`, derived with `calculate_arc_id` from the RO-Crate root `identifier` and
`rdi`, and SHALL return whether the document was created and whether content changed according to its hash. An identical
existing ARC MUST avoid a body write, though timestamp fields MAY be updated.

#### Scenario: Re-submit identical ARC content

- **GIVEN** an ARC document with the same content hash
- **WHEN** it is stored again
- **THEN** the content-changed flag is false and no body write occurs

### Requirement: Verify ARC identity before update

When an ARC document already exists at `arc_{arc_id}` (where `arc_id` is derived with `calculate_arc_id` from the
incoming identifier and `rdi`), the store MUST compare the stored identity to the incoming pair under the same
normalization used by `calculate_arc_id`: whitespace `.strip()` on both identifier and `rdi` only (no Unicode NFC or
other canonicalize-before-hash). Stored identifier MUST be taken from the existing document's RO-Crate content; stored
`rdi` MUST be the document's top-level `rdi` field. If either stripped value differs, the store MUST raise an identity
conflict error, MUST NOT write the document body or metadata update for that attempt, and MUST treat a true
cryptographic hash collision the same as an identity mismatch. Matching identity SHALL continue existing content-hash
and harvest-local duplicate rules unchanged.

#### Scenario: Refuse overwrite on identity mismatch

- **GIVEN** a document at `arc_{arc_id}` whose stripped stored identifier or `rdi` differs from the incoming pair
- **WHEN** `store_arc` is called with an incoming identifier and `rdi` that hash to that same `arc_id`
- **THEN** an identity conflict error is raised
- **AND** the existing document body and metadata remain unchanged

#### Scenario: Matching identity updates normally

- **GIVEN** an existing document whose stripped identifier and `rdi` match the incoming pair
- **WHEN** `store_arc` is called again
- **THEN** no identity conflict is raised
- **AND** content-hash and harvest-local duplicate behavior apply as today

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
transitions. Harvest statistics MUST include every ARC document whose `metadata.last_harvest_id` matches the harvest
being finalized, regardless of how many documents match. The store MUST NOT cap statistics at `default_query_limit` from
a single Mango `_find` page. It MUST append ARC event records and release its HTTP session and database client at
shutdown. An unknown harvest lookup SHALL return nothing so callers can raise `ResourceNotFoundError`.

#### Scenario: Shut down the store

- **GIVEN** a connected document store
- **WHEN** it shuts down
- **THEN** the underlying HTTP session and database client are released

#### Scenario: Statistics beyond default query limit

- **GIVEN** more than `default_query_limit` ARC documents with the same `metadata.last_harvest_id`
- **WHEN** `get_harvest_statistics` runs for that harvest
- **THEN** `arcs_submitted` equals the total number of matching ARC documents
- **AND** `arcs_new`, `arcs_updated`, and `arcs_unchanged` sum to that total using the existing classification rules

### Requirement: Detect content change via arc-content-hash

When deciding whether stored ARC content changed, the document store SHALL compare `content_hash` values computed under
the `arc-content-hash` capability. It MUST NOT treat raw JSON serialization differences that the `arc-content-hash`
capability canonicalizes away as a content change.

#### Scenario: Re-submit after order-only RO-Crate noise

- **GIVEN** an ARC document already stored with a content hash
- **WHEN** the same logical ARC is stored again with only order or serialization differences covered by
  `arc-content-hash`
- **THEN** the content-changed flag is false and no body write occurs
