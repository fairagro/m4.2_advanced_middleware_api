# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
