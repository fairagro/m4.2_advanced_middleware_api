# ARC Store — Delta

## ADDED Requirements

### Requirement: Support optional finalize on ArcStore

The `ArcStore` port SHALL expose a `finalize` operation scoped to an RDI
(`finalize(rdi=…)`). Existing per-ARC backends (`GitRepo`, `GitlabApi`) MUST
implement `finalize` as a successful no-op. Callers MUST be able to invoke
`finalize` after a harvest without branching on backend type. Finalize MUST
NOT take `harvest_id` as a store argument (CouchDB holds latest ARC bodies
only; harvest cannot filter catalog membership).

#### Scenario: Finalize on per-ARC Git backend

- **GIVEN** `git_repo` or `gitlab_api` is the configured store
- **WHEN** `finalize` is invoked for an RDI
- **THEN** the call succeeds without writing a consolidated catalog file

### Requirement: Skip per-ARC Git sync for the consolidated backend

When the consolidated Git backend is configured, harvest ARC ingestion SHALL
persist ARC bodies in the document store only and MUST NOT enqueue per-ARC Git
synchronization tasks. Catalog publication happens exclusively via `finalize`.

#### Scenario: Changed ARC does not enqueue per-ARC Git sync

- **GIVEN** `consolidated_git` is configured
- **WHEN** a harvest submits a new or changed ARC
- **THEN** the ARC is stored in CouchDB and no per-ARC Git sync task is
  dispatched

### Requirement: Publish a byte-stable consolidated RDI catalog file on finalize

On `finalize` for an RDI, the consolidated Git backend SHALL rebuild the
catalog file `{rdi}.json` as a top-level JSON array of Schema.org `Dataset`
objects extracted from **all** current document-store ARC RO-Crate bodies for
that RDI, write the file into the configured shared Git repository, commit, and
push when the remote blob differs. Each finalize Git operation MUST use a
**dedicated ephemeral local clone** (unique temporary directory, deleted after
the operation completes or fails) — MUST NOT reuse a stable shared working copy
across concurrent finalize tasks. The file bytes MUST be deterministic: for
the same set of ARC contents, two rebuilds MUST produce identical bytes
(stable Dataset order by `@id`, canonical JSON serialization with sorted
object keys, no finalize-/build-time timestamps or other volatile fields
injected into the payload). Overlapping finalizes for the same RDI MUST
converge on the document store as the source of truth for current ARC bodies
(last successful push wins on the remote).

#### Scenario: Finalize publishes full RDI catalog

- **GIVEN** CouchDB holds one or more ARCs for RDI `edal`
- **WHEN** `finalize` runs for that RDI
- **THEN** `edal.json` contains the extracted Dataset array for all those ARCs
  and is pushed to the shared remote when bytes differ from the remote file

#### Scenario: Unchanged ARC set yields identical catalog bytes

- **GIVEN** a published `{rdi}.json` built from a fixed set of ARC contents
- **WHEN** a later harvest completes with no ARC content changes and finalize
  rebuilds the catalog
- **THEN** the newly built file bytes are identical to the previous catalog
  bytes and the backend skips commit/push when the remote blob already matches

### Requirement: Extract Schema.org Dataset records from RO-Crate

For each ARC included in a catalog rebuild, the consolidated backend SHALL
extract the Schema.org `Dataset` payload from the ARC’s stored RO-Crate JSON
(using the documented root/`@type` Dataset rule). It MUST NOT require a
separate Schema.org upload API. Missing extractable Dataset content MUST be
treated as a permanent persistence error for that ARC during finalize.

#### Scenario: Extract root Dataset

- **GIVEN** an ARC RO-Crate whose `@graph` contains a Dataset node used as the
  catalog record
- **WHEN** the catalog is rebuilt
- **THEN** that Dataset object appears in `{rdi}.json`

### Requirement: Select exactly one ArcStore backend

Configuration MUST select exactly one ArcStore backend. Preferred form is
`arc_store.type` with value `git_repo`, `gitlab_api`, or `consolidated_git`
and nested settings. Legacy top-level `git_repo` / `gitlab_api` (and any
transitional top-level `consolidated_git`) MUST remain accepted and MUST be
documented as obsolete. Mixing more than one effective backend MUST fail
validation. Dual-write of per-ARC Git projects and consolidated catalog
files in one deployment is out of scope.

#### Scenario: Reject dual backend config

- **GIVEN** more than one effective ArcStore backend is configured (via
  `arc_store` and/or obsolete top-level keys)
- **WHEN** configuration is validated
- **THEN** validation fails before the API starts

#### Scenario: Prefer arc_store.type

- **GIVEN** `arc_store.type` is `consolidated_git` with nested catalog settings
- **WHEN** the factory constructs ArcStore
- **THEN** the consolidated Git implementation is used

### Requirement: Classify consolidated Git failures

The consolidated backend SHALL raise a retryable store error for transient
network, remote, or lock-like Git failures during finalize push. It MUST raise
a permanent store error for invalid credentials, malformed extraction input, or
misconfiguration discovered before Git activity.

#### Scenario: Transient push failure

- **GIVEN** a temporary failure talking to the shared remote
- **WHEN** finalize pushes
- **THEN** a retryable store error is raised
