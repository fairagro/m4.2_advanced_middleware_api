# ARC Store — Delta

## ADDED Requirements

### Requirement: Support optional finalize on ArcStore

The `ArcStore` port SHALL expose a `finalize` operation scoped to an RDI (and
MAY accept harvest context). Existing per-ARC backends (`GitRepo`, `GitlabApi`)
MUST implement `finalize` as a successful no-op. Callers MUST be able to invoke
`finalize` after a harvest without branching on backend type.

#### Scenario: Finalize on per-ARC Git backend

- **GIVEN** `git_repo` or `gitlab_api` is the configured store
- **WHEN** `finalize` is invoked for an RDI
- **THEN** the call succeeds without writing a consolidated catalog file

### Requirement: Stage ARCs in the consolidated Git backend

When the consolidated Git backend is configured, `create_or_update` SHALL
durably record that the ARC/RDI requires inclusion in the next catalog publish
by writing a **CouchDB dirty marker** (not a duplicate ARC body). It MUST NOT
require rewriting the shared RDI catalog file on every individual ARC sync.
Unchanged ARC content (no content-hash change relative to the already stored
document) MUST NOT mark the ARC dirty for catalog publish. Authoritative ARC
RO-Crate bodies remain the normal document-store ARC documents.

#### Scenario: Stage a changed ARC

- **GIVEN** the consolidated Git backend is configured
- **WHEN** a changed ARC is synced with an RDI
- **THEN** a CouchDB dirty marker records that ARC for the RDI without
  publishing `{rdi}.json` and without storing a second full RO-Crate copy

#### Scenario: Skip staging for unchanged content

- **GIVEN** an ARC whose content hash is unchanged
- **WHEN** sync runs on the consolidated backend
- **THEN** staging is not marked dirty for that ARC

### Requirement: Publish a byte-stable consolidated RDI catalog file on finalize

On `finalize` for an RDI, the consolidated Git backend SHALL rebuild the
catalog file `{rdi}.json` as a top-level JSON array of Schema.org `Dataset`
objects extracted from stored ARC RO-Crate content for that RDI, write the
file into the configured shared Git repository, commit, and push. It MUST then
clear dirty markers for that RDI. The file bytes MUST be deterministic: for
the same set of ARC contents, two rebuilds MUST produce identical bytes
(stable Dataset order by `@id`, canonical JSON serialization with sorted
object keys, no finalize-/build-time timestamps or other volatile fields
injected into the payload). Overlapping finalizes for the same RDI MUST
converge on CouchDB as the source of truth for current ARC bodies (last
successful push wins on the remote).

#### Scenario: Finalize publishes catalog

- **GIVEN** one or more dirty-marked ARCs for RDI `edal`
- **WHEN** `finalize` runs for that RDI
- **THEN** `edal.json` contains the extracted Dataset array, is pushed to the
  shared remote, and dirty markers for `edal` are cleared

#### Scenario: Unchanged ARC set yields identical catalog bytes

- **GIVEN** a published `{rdi}.json` built from a fixed set of ARC contents
- **WHEN** a later harvest completes with no ARC content changes and finalize
  rebuilds the catalog
- **THEN** the newly built file bytes are identical to the previous catalog
  bytes and the backend skips commit/push when the remote blob already matches

#### Scenario: Empty dirty set skips publish when bytes match

- **GIVEN** no dirty markers for the RDI and the remote catalog already equals
  a fresh rebuild
- **WHEN** `finalize` runs
- **THEN** the backend skips commit/push and still succeeds

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

Configuration MUST allow at most one of `git_repo`, `gitlab_api`, or
`consolidated_git`. The factory MUST construct the matching `ArcStore`
implementation. Dual-write of per-ARC Git projects and consolidated catalog
files in one deployment is out of scope.

#### Scenario: Reject dual backend config

- **GIVEN** more than one of the mutually exclusive store config keys is set
- **WHEN** configuration is validated
- **THEN** validation fails before the API starts

### Requirement: Classify consolidated Git failures

The consolidated backend SHALL raise a retryable store error for transient
network, remote, or lock-like Git failures during finalize push. It MUST raise
a permanent store error for invalid credentials, malformed extraction input, or
misconfiguration discovered before Git activity.

#### Scenario: Transient push failure

- **GIVEN** a temporary failure talking to the shared remote
- **WHEN** finalize pushes
- **THEN** a retryable store error is raised
