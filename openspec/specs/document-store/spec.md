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
