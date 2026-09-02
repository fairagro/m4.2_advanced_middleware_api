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
objects extracted from current document-store ARC RO-Crate bodies for that RDI
(see partial-push rules below), write the file into the configured shared Git
repository, commit, and push when the remote blob differs. Each finalize Git
operation MUST use a **dedicated ephemeral local clone** (unique temporary
directory, deleted after the operation completes or fails) — MUST NOT reuse a
stable shared working copy across concurrent finalize tasks. The file bytes
MUST be deterministic: for the same set of successfully included ARC contents,
two rebuilds MUST produce identical bytes (stable Dataset order by normalized
`identifier`, with canonical JSON tie-break when `identifier` is missing or
duplicated among included Datasets; canonical JSON serialization with sorted
object keys, no finalize-/build-time timestamps or other volatile fields
injected into the payload). Overlapping
finalizes for the same RDI MUST converge on the document store as the source of
truth for current ARC bodies (last successful push wins on the remote).

**Interim partial push (no last-good; issue #356):** If Dataset extraction or
JSON-LD expand/compact fails for an individual ARC, finalize MUST skip that ARC,
continue with the remaining ARCs, and still publish when at least one Dataset
succeeds. Skips MUST be logged. Until last-good retention exists, a previously
published Dataset MAY disappear from `{rdi}.json` when its current CouchDB body
fails. If the RDI had one or more ARC documents and **all** of them fail,
finalize MUST raise a permanent store error and MUST NOT push an empty catalog
that would wipe the remote. An RDI with zero ARC documents MAY publish an empty
array.

#### Scenario: Finalize publishes full RDI catalog

- **GIVEN** CouchDB holds one or more ARCs for RDI `edal` that all extract and
  normalize successfully
- **WHEN** `finalize` runs for that RDI
- **THEN** `edal.json` contains the extracted Dataset array for all those ARCs
  and is pushed to the shared remote when bytes differ from the remote file

#### Scenario: Partial push skips a failing ARC

- **GIVEN** CouchDB holds a good ARC and a bad ARC (extract or JSON-LD failure)
  for the same RDI
- **WHEN** `finalize` runs
- **THEN** the catalog contains the good Dataset only and is eligible to push
- **AND** the bad ARC is skipped (logged), not aborting the whole finalize

#### Scenario: All ARCs fail — refuse empty wipe

- **GIVEN** CouchDB holds one or more ARCs for an RDI and every ARC fails
  extract or JSON-LD normalize
- **WHEN** `finalize` runs
- **THEN** a permanent store error is raised and no empty catalog is pushed

#### Scenario: Unchanged ARC set yields identical catalog bytes

- **GIVEN** a published `{rdi}.json` built from a fixed set of ARC contents
- **WHEN** a later harvest completes with no ARC content changes and finalize
  rebuilds the catalog
- **THEN** the newly built file bytes are identical to the previous catalog
  bytes and the backend skips commit/push when the remote blob already matches

### Requirement: Extract Schema.org Dataset records from RO-Crate

For each ARC included in a catalog rebuild, the consolidated backend SHALL
extract the Schema.org `Dataset` payload from the ARC’s stored RO-Crate JSON
(using the documented root/`@type` Dataset rule). The extracted Dataset MUST
have a non-empty normalized `identifier` (same rules as the API root entity);
otherwise extraction MUST fail for that ARC. It MUST NOT require a separate
Schema.org upload API. Missing extractable Dataset content MUST skip that ARC
under interim partial-push rules (logged); it MUST NOT by itself abort finalize
when other ARCs succeed. When every ARC fails extraction/normalize, see the
empty-wipe refusal under the publish requirement.

#### Scenario: Extract root Dataset

- **GIVEN** an ARC RO-Crate whose `@graph` contains a Dataset node used as the
  catalog record
- **WHEN** the catalog is rebuilt
- **THEN** that Dataset object appears in `{rdi}.json`

#### Scenario: Skip Dataset without identifier

- **GIVEN** an ARC whose chosen catalog Dataset node has no non-empty
  `identifier`
- **WHEN** finalize rebuilds the catalog
- **THEN** that ARC is skipped (logged) under partial-push rules
- **AND** other valid ARCs may still publish

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
a permanent store error for invalid credentials, misconfiguration discovered
before Git activity, or when every ARC for a non-empty RDI fails
extract/normalize (refusing an empty catalog wipe). Individual malformed ARC
bodies during interim partial push MUST be skipped (logged), not abort the
whole finalize when other ARCs succeed.

#### Scenario: Transient push failure

- **GIVEN** a temporary failure talking to the shared remote
- **WHEN** finalize pushes
- **THEN** a retryable store error is raised

### Requirement: Compact catalog Dataset JSON-LD on worker finalize

When the consolidated backend rebuilds an RDI catalog during **finalize** (Celery
worker), each extracted Schema.org `Dataset` SHALL be JSON-LD-expanded (using
the source document’s `@context`) and then JSON-LD-compacted using a
**vendored** schema.org JSON-LD context document plus a pinned ARC/Bioschemas
extension term map (at least the ARC Lab/Sample terms commonly present in
RO-Crate ARC contexts).

The compacted record MUST **emit** `@context` as
`["https://schema.org", <ARC/Bioschemas extension map>]` (not the source
RO-Crate context, and not an inline copy of the vendored release document). The
vendored file governs compact term choice only. Terms unknown to the processing
context MUST remain as absolute IRIs after compact. Expand/compact MUST NOT run
on the API ingest path. For a fixed ARC body and the same vendored contexts,
two compacted Dataset records MUST be byte-identical under the catalog’s
canonical JSON serialization rules.

#### Scenario: Worker finalize rewrites Dataset context

- **GIVEN** an ARC RO-Crate whose top-level `@context` is an RO-Crate profile
  URL plus ARC/Bioschemas extensions
- **WHEN** catalog finalize rebuilds `{rdi}.json` in the worker
- **THEN** each Dataset’s `@context` is `https://schema.org` plus the
  ARC/Bioschemas extension map and schema.org properties such as `name` remain
  short names

#### Scenario: API ingest does not compact

- **GIVEN** a harvest submits an ARC while `consolidated_git` is configured
- **WHEN** the API stores the ARC in CouchDB
- **THEN** the stored ARC body retains its original `@context` and no
  expand/compact is performed at ingest

#### Scenario: Unknown IRIs survive compact

- **GIVEN** a Dataset property whose IRI is not in the vendored schema.org
  context and not in the pinned ARC/Bioschemas map
- **WHEN** the Dataset is compacted during finalize
- **THEN** that property remains as an absolute IRI key or value in the
  catalog record

#### Scenario: Per-ARC JSON-LD failure does not abort finalize (interim)

- **GIVEN** multiple ARCs for an RDI and one Dataset fails expand/compact
  (e.g. unknown `@context` URL under the offline loader)
- **WHEN** finalize normalizes catalog Datasets
- **THEN** that ARC is skipped (logged) and remaining Datasets are still
  compacted and eligible for catalog publish (partial push; no last-good yet)

### Requirement: Vendor schema.org context offline (no runtime fetch)

The schema.org portion of the compact **processing** context MUST come from a
**vendored** release file shipped with the API package (alongside vendored
RO-Crate contexts). The implementation MUST NOT fetch schema.org over the
network during finalize and MUST NOT expose a configuration option for the
schema.org context version. Upgrading the pin MUST be a deliberate repository
change (replace/rename the vendored file). Loading the vendored document MUST
be process-local and reusable for all Datasets in that process.

#### Scenario: Finalize works without schema.org network access

- **GIVEN** a worker process with no outbound access to schema.org or GitHub
- **WHEN** finalize compacts catalog Datasets
- **THEN** compact uses the vendored schema.org document and succeeds without
  an HTTP fetch

#### Scenario: Same vendored pin yields stable compact

- **GIVEN** a fixed ARC Dataset body and the shipped schema.org vendor file
- **WHEN** finalize compacts the Dataset twice
- **THEN** the compacted Dataset records are byte-identical under catalog
  serialization rules

### Requirement: Materialize referenced entities before catalog JSON-LD normalize

When the consolidated backend rebuilds an RDI catalog during **finalize**
(Celery worker), each extracted root `Dataset` SHALL be enriched from the
source RO-Crate `@graph` so dangling `@id` references become inline objects
**before** JSON-LD expand/compact. Materialization MUST run only on the worker
finalize path and MUST NOT mutate CouchDB ARC bodies or run on API ingest.

The catalog file MUST remain a JSON array of independent `Dataset` records (no
shared top-level `@graph` across all ARCs in `{rdi}.json`).

#### Scenario: Person reference becomes inline creator

- **GIVEN** a root `Dataset` whose `creator` is `{"@id": "#Person_Kevin_Urbasch"}`
  and the RO-Crate `@graph` contains a `Person` node with that `@id` and
  `givenName` / `familyName`
- **WHEN** worker finalize builds the catalog entry for that ARC
- **THEN** the published `creator` includes `givenName` and `familyName`
- **AND** the published `creator` is not solely a fragment `@id` reference

#### Scenario: Author and contributor use the same Person rules

- **GIVEN** a root `Dataset` with `author` or `contributor` referencing a
  `Person` node in `@graph`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published property contains the same inline Person fields as
  `creator`

#### Scenario: LDComment maps to schema.org where possible

- **GIVEN** a root `Dataset` whose `comment` references a `Comment` node with
  `name` matching a known metadata key (for example Keywords or Language) and
  `text` carrying the value
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the catalog entry uses the corresponding first-class schema.org
  property (for example `keywords` or `inLanguage`) when mappable
- **AND** only uses inline `Comment` with `name` and `text` when no mapping
  applies

#### Scenario: License placeholder resolves to text or URL

- **GIVEN** a root `Dataset` whose `license` is `{"@id": "#LICENSE"}` and the
  `@graph` contains a `#LICENSE` node with `url`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `license` is that URL string
- **AND** does not remain `#LICENSE`

#### Scenario: License placeholder with text only

- **GIVEN** a root `Dataset` whose `license` is `{"@id": "#LICENSE"}` and the
  `@graph` `#LICENSE` node has `text` but no `url`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `license` is the license text string
- **AND** does not remain `#LICENSE`

#### Scenario: hasPart includes nested Study and Assay Datasets

- **GIVEN** a root `Dataset` whose `hasPart` references `studies/…/` and
  `assays/…/` `Dataset` nodes in `@graph` with `name`, `identifier`, and
  `additionalType` of `Study` or `Assay`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** each published `hasPart` entry is an inline `Dataset` object with
  those fields
- **AND** a Study entry MAY include nested inline Assay `Dataset` objects in
  its own `hasPart` when referenced in `@graph`

#### Scenario: Citation materializes as ScholarlyArticle without Comment chain

- **GIVEN** a root `Dataset` whose `citation` references a `ScholarlyArticle`
  (or compatible `CreativeWork`) node with `headline` and/or `identifier`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `citation` is an inline object with those fields
- **AND** nested `comment` or status references on the publication node are
  not materialized into the catalog entry

#### Scenario: Missing reference target is omitted

- **GIVEN** a root `Dataset` property referencing an `@id` absent from `@graph`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** that list entry or property value is omitted from the published
  Dataset
- **AND** finalize continues for other ARCs (best-effort materialize)

### Requirement: Do not materialize non-catalog RO-Crate subgraphs

Materialization MUST NOT copy the full RO-Crate `@graph` or follow references
into `LabProcess`, `Sample`, `PropertyValue`, `File`, `LabProtocol`, or
process/protocol subgraphs (for example via `about` on Study nodes). Only the
properties and node types listed in the materialize requirement above SHALL be
followed.

#### Scenario: LabProcess nodes stay out of catalog

- **GIVEN** a Study `Dataset` whose `about` references `LabProcess` nodes
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Study `hasPart` or inline Study object does not
  include those `LabProcess` nodes

### Requirement: Relativize catalog Dataset IDs after JSON-LD compact

When the consolidated backend JSON-LD-expands and compacts a catalog Dataset
on worker finalize, the published Dataset MUST use relative identifiers for
**path-based** values that were relative in the source ARC (root `./`, and
path IDs such as `assays/<id>/` and `studies/<id>/` on `hasPart` children).
Inlined Person and Comment objects materialized for catalog export MUST NOT
retain fragment `@id` values (for example `#Person_…` or `#LDComment_…`); they
SHALL appear as anonymous inline nodes with `@type` and data properties only.
The published Dataset MUST NOT contain the JSON-LD processor dummy base
`http://example.org/base/` (or any path under that origin) in identifier-bearing
fields. Canonical Dataset identity for catalog consumers remains the Dataset
`identifier` property. Expand/compact MUST still run after materialization.

#### Scenario: ARCtrl root Dataset keeps relative root id

- **GIVEN** a Dataset extracted from an ARCtrl-style RO-Crate whose root `@id`
  is `./` and whose `identifier` is a non-empty string
- **WHEN** worker finalize materializes, expands, and compacts that Dataset for
  the catalog
- **THEN** the published Dataset `@id` (and `id` if present) equals `./`
- **AND** the value does not contain `http://example.org/base/`

#### Scenario: Path IDs on hasPart stay relative

- **GIVEN** a materialized `hasPart` child whose source `@id` is a relative
  path such as `studies/AthalianaColdStress/` or `assays/Proteomics_MS/`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** that child's `@id` (or `id`) remains the same relative path
- **AND** does not contain `http://example.org/base/`

#### Scenario: Inlined Person has no fragment id

- **GIVEN** a materialized inline `creator` Person sourced from
  `#Person_Kevin_Urbasch`
- **WHEN** worker finalize expands and compacts the catalog Dataset
- **THEN** the published `creator` object includes `givenName` / `familyName`
- **AND** does not contain `@id` or `id` equal to `#Person_Kevin_Urbasch`

#### Scenario: Absolute IRIs that were already absolute stay absolute

- **GIVEN** a Dataset field whose value is already an absolute HTTP(S) URL
  other than the dummy compact base (for example `sameAs` or DOI)
- **WHEN** worker finalize materializes, expands, and compacts that Dataset
- **THEN** that absolute IRI remains absolute and is not rewritten to a
  relative form

#### Scenario: identifier and schema.org compact are preserved

- **GIVEN** an ARCtrl-style Dataset with `identifier` and schema.org properties
  such as `name`
- **WHEN** worker finalize materializes, expands, and compacts that Dataset
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

### Requirement: Use shallow clones for Git CLI working copies

When the Git CLI backends create a fresh local working copy by cloning a remote,
the clone MUST be shallow with depth 1. The tip working tree MUST still contain
the files needed for catalog finalize and per-ARC sync or get. Tip content after
clone, commit, and push MUST match what a full-history clone would produce for
the same tip-only operations. Empty or missing remotes that fall back to local
repository initialization are unchanged. Operators MUST NOT need a configuration
knob to enable this depth.

#### Scenario: Fresh clone is shallow

- **GIVEN** a Git CLI backend operation that clones into a new local working directory
- **WHEN** the clone completes successfully
- **THEN** the local repository history depth is 1
- **AND** the tip working tree is usable for the operation (read/write tip files,
  commit, and push as applicable)

#### Scenario: Catalog publish result unchanged vs tip-only needs

- **GIVEN** a consolidated catalog remote whose tip already contains `{rdi}.json`
- **WHEN** catalog finalize publishes identical bytes for that RDI
- **THEN** the store skips commit/push as today
- **AND** when bytes differ, the pushed tip file matches the serialized catalog
  bytes

### Requirement: Expose catalog finalize skip outcomes to callers

When the consolidated catalog backend completes a successful `finalize` for an
RDI (including when the remote catalog bytes are unchanged and no Git push
occurs), the operation MUST return enough outcome information for orchestrators
to report how many Datasets were published and which ARCs were skipped under
interim partial-push rules. The outcome MUST include whether a push occurred,
the count of Datasets included in the built catalog, and for each skipped ARC
its `arc_id` and a human-readable reason. Per-ARC Git backends that treat
`finalize` as a no-op MUST return an outcome with no skips and no push.
Failure paths that raise a permanent store error (including all-ARC extract or
normalize failure that refuses an empty wipe) remain exceptions and MUST NOT
pretend success with an empty skip list.

#### Scenario: Successful partial finalize reports skips

- **GIVEN** a consolidated finalize that includes at least one Dataset and skips
  at least one ARC for extract or JSON-LD failure
- **WHEN** finalize completes without raising
- **THEN** the outcome indicates the included Dataset count and lists each
  skipped `arc_id` with a reason
- **AND** the push flag reflects whether remote bytes were updated

#### Scenario: Per-ARC backend finalize outcome is empty

- **GIVEN** a per-ARC Git backend
- **WHEN** finalize runs for an RDI
- **THEN** the outcome reports no push and no skipped ARCs
