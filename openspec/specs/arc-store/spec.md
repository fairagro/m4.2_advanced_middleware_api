# ARC Store

## Purpose

Git-backend ports for parsed ARC objects: a per-ARC `ArcStore` (create/update repositories by `arc_id`) and an optional
`ConsolidatedArcStore` (RDI catalog `finalize`). Both share lifecycle (health / shutdown) only. They do not depend on
Celery, CouchDB, or HTTP; the caller in `arc-manager/` owns parsing, events, and retry policy.

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

### Requirement: Distinct ArcStore and ConsolidatedArcStore ports

The system MUST expose two role ports that share only lifecycle (health and shutdown). The per-ARC port MUST provide
sync ops (`create_or_update` and any get/delete/exists surface). The catalog port MUST provide RDI `finalize` only.
Dual-slot wiring MUST type `arc_store` as the per-ARC port and `consolidated_store` as the catalog port or `None`.

#### Scenario: Factory types match dual slots

- **GIVEN** both slots are configured
- **WHEN** the runtime constructs ArcStore backends for the dual slots
- **THEN** the per-ARC slot instance is the per-ARC port type
- **AND** the consolidated slot instance is the catalog port type

#### Scenario: Catalog port has no per-ARC sync API

- **GIVEN** a configured consolidated catalog backend
- **WHEN** callers sync an ARC via the dual-slot runtime
- **THEN** only the per-ARC slot receives `create_or_update`
- **AND** the catalog port is not used as a per-ARC sync target

#### Scenario: Per-ARC port has no catalog finalize API

- **GIVEN** a configured per-ARC Git backend
- **WHEN** a harvest completes and catalog finalize is enqueued
- **THEN** only the consolidated slot receives `finalize`
- **AND** the per-ARC port is not invoked for catalog publish

### Requirement: Publish a byte-stable consolidated RDI catalog file on finalize

On `finalize` for an RDI, the consolidated Git backend SHALL rebuild the catalog file `{rdi}.json` as a top-level JSON
array of Schema.org `Dataset` objects extracted from current document-store ARC RO-Crate bodies for that RDI (see
partial-push rules below), write the file into the configured shared Git repository, commit, and push when the remote
blob differs. Each finalize Git operation MUST use a **dedicated ephemeral local clone** (unique temporary directory,
deleted after the operation completes or fails) — MUST NOT reuse a stable shared working copy across concurrent finalize
tasks. The file bytes MUST be deterministic: for the same set of successfully included ARC contents, two rebuilds MUST
produce identical bytes (stable Dataset order by normalized `identifier`, with canonical JSON tie-break when
`identifier` is missing or duplicated among included Datasets; canonical JSON serialization with sorted object keys, no
finalize-/build-time timestamps or other volatile fields injected into the payload). Overlapping finalizes for the same
RDI MUST converge on the document store as the source of truth for current ARC bodies (last successful push wins on the
remote).

**Interim partial push (no last-good; issue #356):** If Dataset extraction or JSON-LD expand/compact fails for an
individual ARC, finalize MUST skip that ARC, continue with the remaining ARCs, and still publish when at least one
Dataset succeeds. Skips MUST be logged. Until last-good retention exists, a previously published Dataset MAY disappear
from `{rdi}.json` when its current CouchDB body fails. If the RDI had one or more ARC documents and **all** of them
fail, finalize MUST raise a permanent store error and MUST NOT push an empty catalog that would wipe the remote. An RDI
with zero ARC documents MAY publish an empty array.

#### Scenario: Finalize publishes full RDI catalog

- **GIVEN** CouchDB holds one or more ARCs for RDI `edal` that all extract and normalize successfully
- **WHEN** `finalize` runs for that RDI
- **THEN** `edal.json` contains the extracted Dataset array for all those ARCs and is pushed to the shared remote when
  bytes differ from the remote file

#### Scenario: Partial push skips a failing ARC

- **GIVEN** CouchDB holds a good ARC and a bad ARC (extract or JSON-LD failure) for the same RDI
- **WHEN** `finalize` runs
- **THEN** the catalog contains the good Dataset only and is eligible to push
- **AND** the bad ARC is skipped (logged), not aborting the whole finalize

#### Scenario: All ARCs fail — refuse empty wipe

- **GIVEN** CouchDB holds one or more ARCs for an RDI and every ARC fails extract or JSON-LD normalize
- **WHEN** `finalize` runs
- **THEN** a permanent store error is raised and no empty catalog is pushed

#### Scenario: Unchanged ARC set yields identical catalog bytes

- **GIVEN** a published `{rdi}.json` built from a fixed set of ARC contents
- **WHEN** a later harvest completes with no ARC content changes and finalize rebuilds the catalog
- **THEN** the newly built file bytes are identical to the previous catalog bytes and the backend skips commit/push when
  the remote blob already matches

### Requirement: Release in-memory catalog datasets before Git publish

When the consolidated backend has fully serialized an RDI catalog for finalize, it MUST release the in-memory collection
of included Dataset records before it starts the ephemeral Git clone and push for that attempt. The catalog bytes
written to Git MUST be the deterministic bytes required by **Publish a byte-stable consolidated RDI catalog file on
finalize**. Partial-push skip rules, the empty-catalog wipe refusal, and the finalize outcome (push flag, Dataset count,
skip list) MUST stay the same. Deciding that the remote catalog is unchanged MUST NOT require rebuilding that Dataset
collection.

#### Scenario: Datasets are released before clone

- **GIVEN** a consolidated finalize that serializes one or more included Datasets
- **WHEN** the ephemeral Git clone for that attempt starts
- **THEN** the in-memory Dataset collection built for that serialization is no longer retained
- **AND** the catalog file bytes match a rebuild from the same included ARC contents

#### Scenario: Unchanged catalog still skips push

- **GIVEN** a serialized catalog whose bytes already match the remote catalog file
- **WHEN** finalize compares the remote file to that serialization
- **THEN** no commit or push is performed
- **AND** the comparison does not rebuild the Dataset collection

#### Scenario: All ARC failures still refuse an empty wipe

- **GIVEN** an RDI with one or more ARC documents that all fail extract or normalize
- **WHEN** finalize runs
- **THEN** a permanent store error is raised
- **AND** no catalog push occurs

### Requirement: Extract Schema.org Dataset records from RO-Crate

For each ARC included in a catalog rebuild, the consolidated backend SHALL extract the Schema.org `Dataset` payload from
the ARC’s stored RO-Crate JSON (using the documented root/`@type` Dataset rule). The extracted Dataset MUST have a
non-empty normalized `identifier` (same rules as the API root entity); otherwise extraction MUST fail for that ARC. It
MUST NOT require a separate Schema.org upload API. Missing extractable Dataset content MUST skip that ARC under interim
partial-push rules (logged); it MUST NOT by itself abort finalize when other ARCs succeed. When every ARC fails
extraction/normalize, see the empty-wipe refusal under the publish requirement.

#### Scenario: Extract root Dataset

- **GIVEN** an ARC RO-Crate whose `@graph` contains a Dataset node used as the catalog record
- **WHEN** the catalog is rebuilt
- **THEN** that Dataset object appears in `{rdi}.json`

#### Scenario: Skip Dataset without identifier

- **GIVEN** an ARC whose chosen catalog Dataset node has no non-empty `identifier`
- **WHEN** finalize rebuilds the catalog
- **THEN** that ARC is skipped (logged) under partial-push rules
- **AND** other valid ARCs may still publish

### Requirement: Dual ArcStore configuration slots

Configuration MUST provide a **required** `arc_store` slot for per-ARC Git persistence and MAY provide an **optional**
`consolidated_store` slot for the shared RDI catalog. The `arc_store` backend MUST be configured via nested `git_repo`
settings (exactly that key). There MUST NOT be a separate `type` discriminator field on either slot. The
`consolidated_store` slot MUST configure consolidated catalog settings under `consolidated_git` (slot name selects the
catalog role). Putting catalog settings under `arc_store` MUST fail validation. Nested `gitlab_api` under `arc_store`
MUST fail validation. Top-level `git_repo`, `gitlab_api`, and `consolidated_git` MUST NOT be model fields (they are not
accepted as configuration). Config that relies only on those keys MUST fail on the API config model (required
`arc_store` missing and/or unknown top-level fields forbidden). The API `Config` model MUST reject unknown top-level
fields (`extra="forbid"`). The worker `WorkerConfig` projection MUST ignore API-only keys from the same shared flat file
(it is not a second full schema). Each slot MAY carry its own `git` CLI settings object using the shared Git CLI
settings type.

#### Scenario: Accept GitRepo plus optional catalog

- **GIVEN** `arc_store.git_repo` is set with nested settings and `consolidated_store` is set
- **WHEN** configuration is validated
- **THEN** validation succeeds and both slots are available to the runtime

#### Scenario: Reject catalog settings under arc_store

- **GIVEN** `arc_store` contains only `consolidated_git` (no `git_repo`)
- **WHEN** configuration is validated
- **THEN** validation fails before the API or worker starts

#### Scenario: Reject nested gitlab_api under arc_store

- **GIVEN** `arc_store` contains nested `gitlab_api` (with or without `git_repo`)
- **WHEN** configuration is validated
- **THEN** validation fails before the API or worker starts

#### Scenario: Obsolete top-level store keys are not configuration

- **GIVEN** only a top-level `git_repo`, `gitlab_api`, or `consolidated_git` key is provided (no `arc_store`)
- **WHEN** configuration is validated
- **THEN** validation fails (unknown top-level fields and/or missing required `arc_store`)

#### Scenario: Reject unknown top-level fields alongside dual slots

- **GIVEN** API `Config` validation with `arc_store` configured and an unknown top-level field also present
- **WHEN** configuration is validated
- **THEN** validation fails before the API starts

#### Scenario: Worker projection ignores API-only keys

- **GIVEN** the shared flat config includes API-only fields such as `client_auth_oid` plus a valid `arc_store`
- **WHEN** `WorkerConfig` is validated
- **THEN** validation succeeds and API-only fields are ignored

### Requirement: Role-based ArcStore operations

The per-ARC `arc_store` (typed as the per-ARC `ArcStore` port) MUST perform per-ARC `create_or_update` (Git sync). The
optional `consolidated_store` (typed as `ConsolidatedArcStore | None`), when configured, MUST perform RDI `finalize` for
catalog publish. The system MUST NOT invoke catalog `finalize` on the per-ARC store as the catalog implementation, and
MUST NOT invoke per-ARC `create_or_update` on the consolidated store for sync. When `consolidated_store` is absent, the
system MUST NOT enqueue catalog finalize. There is **no** cross-store ordering guarantee between per-ARC sync completion
and catalog finalize; catalog rebuild MUST use document-store ARC bodies for the RDI.

#### Scenario: Sync uses only arc_store

- **GIVEN** both slots are configured
- **WHEN** a worker runs per-ARC Git sync
- **THEN** only `arc_store` receives `create_or_update`
- **AND** `consolidated_store` is not called for that sync

#### Scenario: Finalize uses only consolidated_store

- **GIVEN** `consolidated_store` is configured
- **WHEN** a worker runs catalog finalize for an RDI
- **THEN** only `consolidated_store` receives `finalize`
- **AND** `arc_store` is not used as the catalog publisher

#### Scenario: No finalize enqueue without consolidated_store

- **GIVEN** only `arc_store` is configured
- **WHEN** a harvest transitions to `COMPLETED`
- **THEN** no catalog finalize task is enqueued

### Requirement: Dual-slot Git backend health checks

When global Git-backend health checks are enabled, the system MUST include a check keyed `git_backend` for the required
`arc_store` slot. When `consolidated_store` is also configured, the system MUST include a separate check keyed
`consolidated_store`. There MUST NOT be a separate feature flag solely to disable the consolidated health check.
Aggregate global health status MUST fail when any included check is false (same aggregation as other health services).

#### Scenario: Both backends appear when consol. configured

- **GIVEN** git-backend global health is enabled and both slots are configured
- **WHEN** `/v3/health` runs
- **THEN** the response includes distinct checks for `git_backend` and `consolidated_store`
- **AND** if either is false, overall health is ERROR

### Requirement: Classify consolidated Git failures

The consolidated backend SHALL raise a retryable store error for transient network, remote, or lock-like Git failures
during finalize push. It MUST raise a permanent store error for invalid credentials, misconfiguration discovered before
Git activity, or when every ARC for a non-empty RDI fails extract/normalize (refusing an empty catalog wipe). Individual
malformed ARC bodies during interim partial push MUST be skipped (logged), not abort the whole finalize when other ARCs
succeed.

#### Scenario: Transient push failure

- **GIVEN** a temporary failure talking to the shared remote
- **WHEN** finalize pushes
- **THEN** a retryable store error is raised

### Requirement: Compact catalog Dataset JSON-LD on worker finalize

When the consolidated backend rebuilds an RDI catalog during **finalize** (Celery worker), each extracted Schema.org
`Dataset` SHALL be JSON-LD-expanded (using the source document’s `@context`) and then JSON-LD-compacted using a
**vendored** schema.org JSON-LD context document plus a pinned ARC/Bioschemas extension term map (at least the ARC
Lab/Sample terms commonly present in RO-Crate ARC contexts) plus a transitional **catalog dump-shape** extension that
overrides date-term typing and list `@container` rules for Search Hub–stable basic-layout dumps (not AgriSchemas).

The compacted record MUST **emit** `@context` as
`["https://schema.org", <ARC/Bioschemas extension map>, <catalog dump-shape map>]` (not the source RO-Crate context, and
not an inline copy of the vendored release document). The vendored file plus those extensions govern compact term
choice. Terms unknown to the processing context MUST remain as absolute IRIs after compact. Expand/compact MUST NOT run
on the API ingest path. For a fixed ARC body and the same vendored contexts, two compacted Dataset records MUST be
byte-identical under the catalog’s canonical JSON serialization rules.

#### Scenario: Worker finalize rewrites Dataset context

- **GIVEN** an ARC RO-Crate whose top-level `@context` is an RO-Crate profile URL plus ARC/Bioschemas extensions
- **WHEN** catalog finalize rebuilds `{rdi}.json` in the worker
- **THEN** each Dataset’s `@context` is `https://schema.org` plus the ARC/Bioschemas extension map plus the catalog
  dump-shape map and schema.org properties such as `name` remain short names

#### Scenario: API ingest does not compact

- **GIVEN** a harvest submits an ARC while `consolidated_git` is configured
- **WHEN** the API stores the ARC in CouchDB
- **THEN** the stored ARC body retains its original `@context` and no expand/compact is performed at ingest

#### Scenario: Unknown IRIs survive compact

- **GIVEN** a Dataset property whose IRI is not in the vendored schema.org context and not in the pinned ARC/Bioschemas
  map
- **WHEN** the Dataset is compacted during finalize
- **THEN** that property remains as an absolute IRI key or value in the catalog record

#### Scenario: Per-ARC JSON-LD failure does not abort finalize (interim)

- **GIVEN** multiple ARCs for an RDI and one Dataset fails expand/compact (e.g. unknown `@context` URL under the offline
  loader)
- **WHEN** finalize normalizes catalog Datasets
- **THEN** that ARC is skipped (logged) and remaining Datasets are still compacted and eligible for catalog publish
  (partial push; no last-good yet)

### Requirement: Vendor schema.org context offline (no runtime fetch)

The schema.org portion of the compact **processing** context MUST come from a **vendored** release file shipped with the
API package (alongside vendored RO-Crate contexts). The implementation MUST NOT fetch schema.org over the network during
finalize and MUST NOT expose a configuration option for the schema.org context version. Upgrading the pin MUST be a
deliberate repository change (replace/rename the vendored file). Loading the vendored document MUST be process-local and
reusable for all Datasets in that process.

#### Scenario: Finalize works without schema.org network access

- **GIVEN** a worker process with no outbound access to schema.org or GitHub
- **WHEN** finalize compacts catalog Datasets
- **THEN** compact uses the vendored schema.org document and succeeds without an HTTP fetch

#### Scenario: Same vendored pin yields stable compact

- **GIVEN** a fixed ARC Dataset body and the shipped schema.org vendor file
- **WHEN** finalize compacts the Dataset twice
- **THEN** the compacted Dataset records are byte-identical under catalog serialization rules

### Requirement: Materialize referenced entities before catalog JSON-LD normalize

When the consolidated backend rebuilds an RDI catalog during **finalize** (Celery worker), each extracted root `Dataset`
SHALL be enriched from the source RO-Crate `@graph` so dangling `@id` references become inline objects **before**
JSON-LD expand/compact. Materialization MUST run only on the worker finalize path and MUST NOT mutate CouchDB ARC bodies
or run on API ingest.

The catalog file MUST remain a JSON array of independent `Dataset` records (no shared top-level `@graph` across all ARCs
in `{rdi}.json`).

#### Scenario: Person reference becomes inline creator

- **GIVEN** a root `Dataset` whose `creator` is `{"@id": "#Person_Kevin_Urbasch"}` and the RO-Crate `@graph` contains a
  `Person` node with that `@id` and `givenName` / `familyName`
- **WHEN** worker finalize builds the catalog entry for that ARC
- **THEN** the published `creator` includes `givenName` and `familyName`
- **AND** the published `creator` is not solely a fragment `@id` reference

#### Scenario: Author and contributor use the same Person rules

- **GIVEN** a root `Dataset` with `author` or `contributor` referencing a `Person` node in `@graph`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published property contains the same inline Person fields as `creator`

#### Scenario: LDComment maps to schema.org where possible

- **GIVEN** a root `Dataset` whose `comment` references a `Comment` node with `name` matching a known metadata key (for
  example Keywords or Language) and `text` carrying the value
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the catalog entry uses the corresponding first-class schema.org property (for example `keywords` or
  `inLanguage`) when mappable
- **AND** only uses inline `Comment` with `name` and `text` when no mapping applies

#### Scenario: License placeholder resolves to text or URL

- **GIVEN** a root `Dataset` whose `license` is `{"@id": "#LICENSE"}` and the `@graph` contains a `#LICENSE` node with
  `url`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `license` is that URL string
- **AND** does not remain `#LICENSE`

#### Scenario: License placeholder with text only

- **GIVEN** a root `Dataset` whose `license` is `{"@id": "#LICENSE"}` and the `@graph` `#LICENSE` node has `text` but no
  `url`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `license` is the license text string
- **AND** does not remain `#LICENSE`

#### Scenario: hasPart includes nested Study and Assay Datasets

- **GIVEN** a root `Dataset` whose `hasPart` references `studies/…/` and `assays/…/` `Dataset` nodes in `@graph` with
  `name`, `identifier`, and `additionalType` of `Study` or `Assay`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** each published `hasPart` entry is an inline `Dataset` object with those fields
- **AND** a Study entry MAY include nested inline Assay `Dataset` objects in its own `hasPart` when referenced in
  `@graph`

#### Scenario: Citation materializes as ScholarlyArticle without Comment chain

- **GIVEN** a root `Dataset` whose `citation` references a `ScholarlyArticle` (or compatible `CreativeWork`) node with
  `headline` and/or `identifier`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published `citation` is an inline object with those fields
- **AND** nested `comment` or status references on the publication node are not materialized into the catalog entry

#### Scenario: Missing reference target is omitted

- **GIVEN** a root `Dataset` property referencing an `@id` absent from `@graph`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** that list entry or property value is omitted from the published Dataset
- **AND** finalize continues for other ARCs (best-effort materialize)

### Requirement: Materialize Creator Organization Comments as schema.org Organization creators

When worker finalize materializes a catalog Dataset, Comments named `Creator Organization` (case-insensitive) SHALL
become schema.org `Organization` objects on Dataset `creator` **alongside** any Person creators. Names come from Comment
`text` (`; `-segments and/or multiple nodes, encounter order). Mapped Comments MUST NOT remain opaque Dataset `comment`
entries. Each Organization MUST have `@type` `Organization` and `name`, omit fragment `@id`s, and follow `creator`
list/object normalization.

#### Scenario: Organization creators appear beside Person creators

- **GIVEN** a root Dataset with a Person `creator` reference and a `comment` referencing a Comment named
  `Creator Organization` whose text is an organisation label
- **WHEN** worker finalize materializes the catalog entry
- **THEN** published `creator` includes the inline Person **and** an `Organization` with that `name`
- **AND** the `Creator Organization` Comment is not retained as an opaque Dataset `comment` entry

#### Scenario: Organization-only creators when no Person exists

- **GIVEN** a root Dataset with no Person `creator` and a `Creator Organization` Comment
- **WHEN** worker finalize materializes the catalog entry
- **THEN** published `creator` includes the `Organization`

### Requirement: Pair Creator Organization URL Comments by parallel index

Comment nodes whose `name` matches `Creator Organization URL` (case-insensitive) SHALL supply URLs for the organisations
produced under the Creator Organization materialize requirement. URL texts MAY use `; ` segmentation. URLs pair with
organisation names by parallel index after flattening both lists in encounter order. Unpaired names still publish
without `url`; extra URLs are ignored. Mapped URL Comments MUST NOT remain as opaque Dataset `comment` entries.

#### Scenario: Semicolon-joined organisations and parallel URLs

- **GIVEN** Comment `Creator Organization` text `Org A; Org B` and Comment `Creator Organization URL` text
  `https://a.example; https://b.example`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** published `creator` includes two `Organization` objects with names `Org A` / `Org B` and matching `url`
  values

#### Scenario: URL optional per organisation

- **GIVEN** Comment `Creator Organization` text `Org A; Org B` and a single `Creator Organization URL` segment for
  `Org A` only
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the first Organization has `url` and the second Organization has `name` only

### Requirement: Materialize Landing Page Comment as Dataset url

When worker finalize materializes a catalog Dataset, Comments named `Landing Page` (case-insensitive) SHALL set Dataset
`url` to `{"@id": "<text>"}` when `url` is absent and `text` is non-empty, MUST NOT overwrite an existing `url`, MUST
consume the Comment from opaque `comment` entries, and MUST NOT invent `url` without that Comment. ARC bodies stay
unchanged.

#### Scenario: Landing Page Comment becomes Dataset url

- **GIVEN** a root Dataset without `url` whose `comment` references a Comment named `Landing Page` with non-empty `text`
  `https://example.org/landing`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset has `url` as `{"@id": "https://example.org/landing"}` before compact (and the `url`
  term after compact)
- **AND** the `Landing Page` Comment is not retained as an opaque Dataset `comment` entry

#### Scenario: Existing url is not overwritten

- **GIVEN** a root Dataset that already has `url` and a `Landing Page` Comment with different `text`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset `url` is unchanged
- **AND** the `Landing Page` Comment is not retained as an opaque Dataset `comment` entry

#### Scenario: No Landing Page Comment leaves url unset

- **GIVEN** a root Dataset without `url` and without a `Landing Page` Comment
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset has no `url` property invented by materialize

### Requirement: Derive root spatialCoverage from Study Bounding Box parameters

When worker finalize materializes a catalog Dataset and root `spatialCoverage` is absent, it SHALL collect
ParameterValues named `Bounding Box` (case-insensitive) reachable from root `hasPart` Studies via `about` → `LabProcess`
→ `parameterValue`, parse `value` as schema.org `GeoShape.box` order (south west north east; string or four-number
list), and set `spatialCoverage` to one `Place` → `GeoShape.box` for the axis-aligned union in that same order. Skip
invalid/empty values; do not invent coverage; do not mutate CouchDB ARC bodies. Source-specific encodings (for example
INSPIRE west/south/east/north) are a harvester concern before the ARC is written.

#### Scenario: Union of Study Bounding Box parameters becomes spatialCoverage

- **GIVEN** a root Dataset without `spatialCoverage` whose `hasPart` Studies reach LabProcess ParameterValues named
  `Bounding Box` with parseable schema.org values `48 8 49 9` and `48.5 8.5 50 10`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset `spatialCoverage` is a `Place` with `geo` `GeoShape.box` equal to the union envelope
  `48 8 50 10`

#### Scenario: No parseable Bounding Box leaves spatialCoverage unset

- **GIVEN** a root Dataset without `spatialCoverage` and no reachable parseable `Bounding Box` ParameterValues
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset has no `spatialCoverage` property invented by materialize

### Requirement: Preserve existing spatialCoverage and Study hasPart shape for Bounding Box derivation

When deriving Bounding Box coverage, finalize MUST NOT overwrite an existing root `spatialCoverage` and MUST NOT add
`spatialCoverage` to catalog `hasPart` Study/Assay objects solely from this derivation.

#### Scenario: Existing spatialCoverage is not overwritten

- **GIVEN** a root Dataset that already has `spatialCoverage` and reachable `Bounding Box` ParameterValues
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset `spatialCoverage` is unchanged

#### Scenario: hasPart Studies do not gain spatialCoverage from this derivation

- **GIVEN** a root Dataset with reachable `Bounding Box` ParameterValues and a `hasPart` Study reference
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published root may have derived `spatialCoverage`
- **AND** the inline `hasPart` Study object does not include a `spatialCoverage` property solely from this derivation

### Requirement: Do not materialize non-catalog RO-Crate subgraphs

Materialization MUST NOT copy the full RO-Crate `@graph` or **emit** `LabProcess`, `Sample`, `PropertyValue`, `File`,
`LabProtocol`, or process/protocol subgraphs into the published catalog Dataset. Finalize MAY **read** `LabProcess` /
ParameterValue (`PropertyValue`) nodes solely to derive root `spatialCoverage` under the Bounding Box requirement; those
nodes MUST NOT appear in the published Dataset or its `hasPart` tree.

#### Scenario: LabProcess nodes stay out of catalog

- **GIVEN** a Study `Dataset` whose `about` references `LabProcess` nodes
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Study `hasPart` or inline Study object does not include those `LabProcess` nodes

#### Scenario: ParameterValue read for Bounding Box does not emit PropertyValue

- **GIVEN** LabProcess ParameterValues named `Bounding Box` used to derive root `spatialCoverage`
- **WHEN** worker finalize materializes the catalog entry
- **THEN** the published Dataset does not contain those ParameterValue / PropertyValue nodes as nested objects

### Requirement: Relativize catalog Dataset IDs after JSON-LD compact

When the consolidated backend JSON-LD-expands and compacts a catalog Dataset on worker finalize, the published Dataset
MUST use relative identifiers for **path-based** values that were relative in the source ARC (root `./`, and path IDs
such as `assays/<id>/` and `studies/<id>/` on `hasPart` children). Inlined Person and Comment objects materialized for
catalog export MUST NOT retain fragment `@id` values (for example `#Person_…` or `#LDComment_…`); they SHALL appear as
anonymous inline nodes with `@type` and data properties only. The published Dataset MUST NOT contain the JSON-LD
processor dummy base `http://example.org/base/` (or any path under that origin) in identifier-bearing fields. Canonical
Dataset identity for catalog consumers remains the Dataset `identifier` property. Expand/compact MUST still run after
materialization.

#### Scenario: ARCtrl root Dataset keeps relative root id

- **GIVEN** a Dataset extracted from an ARCtrl-style RO-Crate whose root `@id` is `./` and whose `identifier` is a
  non-empty string
- **WHEN** worker finalize materializes, expands, and compacts that Dataset for the catalog
- **THEN** the published Dataset `@id` (and `id` if present) equals `./`
- **AND** the value does not contain `http://example.org/base/`

#### Scenario: Path IDs on hasPart stay relative

- **GIVEN** a materialized `hasPart` child whose source `@id` is a relative path such as `studies/AthalianaColdStress/`
  or `assays/Proteomics_MS/`
- **WHEN** worker finalize expands and compacts that Dataset
- **THEN** that child's `@id` (or `id`) remains the same relative path
- **AND** does not contain `http://example.org/base/`

#### Scenario: Inlined Person has no fragment id

- **GIVEN** a materialized inline `creator` Person sourced from `#Person_Kevin_Urbasch`
- **WHEN** worker finalize expands and compacts the catalog Dataset
- **THEN** the published `creator` object includes `givenName` / `familyName`
- **AND** does not contain `@id` or `id` equal to `#Person_Kevin_Urbasch`

#### Scenario: Absolute IRIs that were already absolute stay absolute

- **GIVEN** a Dataset field whose value is already an absolute HTTP(S) URL other than the dummy compact base (for
  example `sameAs` or DOI)
- **WHEN** worker finalize materializes, expands, and compacts that Dataset
- **THEN** that absolute IRI remains absolute and is not rewritten to a relative form

#### Scenario: identifier and schema.org compact are preserved

- **GIVEN** an ARCtrl-style Dataset with `identifier` and schema.org properties such as `name`
- **WHEN** worker finalize materializes, expands, and compacts that Dataset
- **THEN** `identifier` equals the source value
- **AND** schema.org properties remain short names as required by catalog compact

### Requirement: Do not emit compact @base in public catalog context

The `@context` written into each published catalog Dataset MUST remain
`["https://schema.org", <ARC/Bioschemas extension map>, <catalog dump-shape map>]`. It MUST NOT include `@base` and MUST
NOT include `http://example.org/base/` or `example.org`.

#### Scenario: Public context has no @base

- **GIVEN** a Dataset compacted for catalog publish
- **WHEN** the Dataset is written into `{rdi}.json`
- **THEN** its `@context` is the schema.org IRI plus the ARC/Bioschemas extension map plus the catalog dump-shape map
- **AND** `@context` does not contain `@base`
- **AND** `@context` does not contain `example.org`

### Requirement: Use unique ephemeral local Git working directories for GitRepo

For the per-ARC Git CLI backend, each create-or-update or get operation that uses a local clone SHALL allocate a working
directory under the configured cache directory that is unique to that invocation. The store MUST NOT reuse a fixed path
keyed only by `arc_id` for concurrent local clones. After the operation completes or fails, the store MUST remove that
working directory. The remote repository identity remains `arc_id`; only the local path is ephemeral.

#### Scenario: Concurrent syncs for the same ARC

- **GIVEN** two overlapping create-or-update operations for the same `arc_id` on one host
- **WHEN** each allocates a local Git working directory
- **THEN** the two working directory paths are distinct
- **AND** neither operation deletes or overwrites the other's working tree

#### Scenario: Cleanup after sync

- **GIVEN** a create-or-update that finished (success or failure)
- **WHEN** the operation returns
- **THEN** that invocation's working directory no longer exists under the cache directory

### Requirement: Reclaim stale ephemeral Git cache directories

The Git CLI backends that place ephemeral clones under the shared cache directory SHALL best-effort remove orphan
directories left by crashed or interrupted operations. Cleanup MUST only target known ephemeral name patterns (and
legacy per-`arc_id` directories from prior deployments) that are older than a configured age threshold. Cleanup MUST NOT
remove directories that are younger than that threshold or that do not match those patterns.

#### Scenario: Stale orphan is removed

- **GIVEN** a cache directory containing an orphan ephemeral working directory older than the age threshold
- **WHEN** reclaim runs
- **THEN** that directory is deleted

#### Scenario: Active or recent workdir is preserved

- **GIVEN** a cache directory containing an ephemeral working directory younger than the age threshold
- **WHEN** reclaim runs
- **THEN** that directory remains

### Requirement: Bound graceful Git executor shutdown

When a Git-backed store shuts down while Git work is in flight, it MUST wait up to a finite bound for that work to
finish, including removal of the ephemeral working directory for that attempt. Work that has not started MUST NOT start.
When the bound expires, shutdown MUST return even if work is still running. Shutdown MUST NOT wait without a bound.
Directories left behind stay subject to **Reclaim stale ephemeral Git cache directories**.

#### Scenario: In-flight work finishes within the bound

- **GIVEN** a Git-backed store with one in-flight operation that removes its ephemeral working directory when it
  finishes
- **WHEN** the store shuts down and that operation finishes before the bound
- **THEN** shutdown waits until the operation has finished
- **AND** the ephemeral working directory for that operation is gone

#### Scenario: Shutdown returns when the bound expires

- **GIVEN** a Git-backed store with one in-flight operation that does not finish
- **WHEN** the store shuts down and the bound expires
- **THEN** shutdown returns
- **AND** it does not wait further for that operation

#### Scenario: Work that has not started does not start

- **GIVEN** a Git-backed store with one operation that has not started
- **WHEN** the store shuts down
- **THEN** that operation does not run

### Requirement: Log a failed ephemeral workdir delete

When a Git-backed store fails to remove an ephemeral working directory, it MUST log a warning that identifies that
directory. The failure MUST NOT by itself fail the Git operation that already finished, and it MUST NOT by itself fail
store shutdown.

#### Scenario: Delete failure after a finished publish is a warning

- **GIVEN** a catalog or per-ARC Git operation that has already finished its Git work
- **WHEN** removing its ephemeral working directory fails
- **THEN** a warning is logged that identifies the directory
- **AND** the Git operation's outcome is unchanged

#### Scenario: Delete failure does not fail shutdown

- **GIVEN** a store shutdown that is waiting for in-flight Git work
- **WHEN** that work fails to remove its ephemeral working directory
- **THEN** a warning is logged
- **AND** shutdown still completes

### Requirement: Use shallow clones for Git CLI working copies

When the Git CLI backends create a fresh local working copy by cloning a remote, the clone MUST be shallow with depth 1.
The tip working tree MUST still contain the files needed for catalog finalize and per-ARC sync or get. Tip content after
clone, commit, and push MUST match what a full-history clone would produce for the same tip-only operations. A soft
not-found clone failure (empty or missing remote) MUST still fall back to local repository initialization. Any other
clone `GitCommandError` MUST propagate and MUST NOT initialize an empty local repository. Transient clone failures
remain retryable store errors. Operators MUST NOT need a configuration knob to enable this depth.

#### Scenario: Soft not-found clone initializes a local repo

- **GIVEN** a Git CLI backend operation that clones into a new local working directory
- **WHEN** the clone fails because the remote or branch is not found
- **THEN** the store initializes a local repository with `origin` set to that remote

#### Scenario: Non-soft clone failure does not initialize

- **GIVEN** a Git CLI backend operation that clones into a new local working directory
- **WHEN** the clone fails with a Git error that is not a soft not-found and not transient
- **THEN** that error propagates
- **AND** no empty local repository is initialized

#### Scenario: Fresh clone is shallow

- **GIVEN** a Git CLI backend operation that clones into a new local working directory
- **WHEN** the clone completes successfully
- **THEN** the local repository history depth is 1
- **AND** the tip working tree is usable for the operation (read/write tip files, commit, and push as applicable)

#### Scenario: Catalog publish result unchanged vs tip-only needs

- **GIVEN** a consolidated catalog remote whose tip already contains `{rdi}.json`
- **WHEN** catalog finalize publishes identical bytes for that RDI
- **THEN** the store skips commit/push as today
- **AND** when bytes differ, the pushed tip file matches the serialized catalog bytes

### Requirement: Catalog finalize skip outcomes on ConsolidatedArcStore

When the consolidated catalog backend completes a successful `finalize` for an RDI (including when remote catalog bytes
are unchanged), the operation MUST return whether a push occurred, the included Dataset count, and each skipped ARC’s
`arc_id` with a human-readable reason. Permanent store errors (including all-ARC failure that refuses an empty wipe)
MUST remain exceptions and MUST NOT pretend success with an empty skip list.

#### Scenario: Successful partial finalize reports skips

- **GIVEN** a consolidated finalize that includes at least one Dataset and skips at least one ARC for extract or JSON-LD
  failure
- **WHEN** finalize completes without raising
- **THEN** the outcome indicates the included Dataset count and lists each skipped `arc_id` with a reason
- **AND** the push flag reflects whether remote bytes were updated

### Requirement: Carry authenticated Git remotes as redacting URL values

When the ArcStore Git backends produce or hold an authenticated HTTP(S) remote URL (token embedded in userinfo), that
value MUST be represented as the shared redacting URL type. Ordinary string conversion of that value MUST NOT expose
userinfo. Passing the URL to Git CLI / GitPython MUST use the explicit unredacted accessor. Plain authenticated remote
URLs as bare strings MUST NOT be the default hand-off into logging, tracing attributes, or similar diagnostic surfaces
owned by the store.

#### Scenario: Authenticated remote stringifies without credentials

- **GIVEN** an ArcStore Git backend has built an authenticated HTTPS remote
- **WHEN** that remote is converted with ordinary string conversion for a diagnostic attribute or log argument
- **THEN** userinfo credentials are not present in the resulting text

#### Scenario: Git operations receive the unredacted remote

- **GIVEN** an authenticated remote URL value
- **WHEN** a clone, fetch, push, or ls-remote is invoked against that remote
- **THEN** Git receives the full URL including credentials via the explicit unredacted accessor

### Requirement: Single-flight critical section for consolidated finalize per RDI

When the consolidated Git backend runs `finalize` for an RDI, the rebuild-through-push **critical section** for that RDI
MUST be single-flight across concurrent callers: at most one such critical section may execute at a time per RDI.
Ephemeral per-call clones and byte-stable catalog rules from **Publish a byte-stable consolidated RDI catalog file on
finalize** remain in force. Overlapping callers MUST wait (bounded) or otherwise serialize rather than racing solely on
Git non-fast-forward. Last-successful-push semantics for conflicts with **external** writers are unchanged.

#### Scenario: Concurrent finalize for one RDI does not parallelize push work

- **GIVEN** two concurrent consolidated `finalize` invocations for the same RDI
- **WHEN** both enter rebuild/push
- **THEN** their critical sections for that RDI do not run in parallel

### Requirement: Lightweight GitLab project existence probe

The GitLab-backed remote provider used by the per-ARC store MUST expose a read-only check that reports whether a project
for a given `arc_id` exists under the configured group and is usable (not pending deletion / not renamed for deletion).
The check MUST use the GitLab HTTP API and MUST NOT run git CLI commands. The check MUST NOT create or modify projects.

#### Scenario: Existing project reports present

- **GIVEN** a GitLab project whose path equals the ARC id under the configured group
- **WHEN** the existence probe runs
- **THEN** it reports that the project exists

#### Scenario: Missing or pending-deletion reports absent

- **GIVEN** no project for the ARC id, or a project marked for deletion / deletion-scheduled path rewrite
- **WHEN** the existence probe runs
- **THEN** it reports that the project does not exist (usable)

### Requirement: Filesystem ARC persistence for local offline stand-in

The local offline stand-in MUST persist ARCs under a configured local output root using arctrl write semantics and MUST
NOT require a Git remote or DataHUB. Path segments derived from ARC identifiers MUST stay contained under the output
root (unsafe or empty identifiers MUST fall back to a generated safe id). Catalog finalize for this persistence path MAY
be a successful no-op in this change.

#### Scenario: Create or update writes an ARC tree under the output root

- **GIVEN** filesystem persistence with a configured output root
- **WHEN** an ARC create-or-update succeeds
- **THEN** an ARC directory tree for that ARC exists under the output root

#### Scenario: Unsafe identifier does not escape the output root

- **GIVEN** filesystem persistence with a configured output root
- **WHEN** create-or-update is called with an identifier that would escape that root
- **THEN** the writer uses a generated safe id under the output root
- **OR** rejects the write without writing outside the output root

#### Scenario: No Git remote required

- **GIVEN** filesystem persistence for the local offline stand-in
- **WHEN** health or create-or-update runs
- **THEN** no Git remote or DataHUB connectivity is required

### Requirement: Unique Comment names per holder before Git Write

Immediately before materializing an ARC into a Git working tree via `ARC.Write`, the Git store SHALL ensure that each
Comment holder — Investigation (ARC root comments), Study, Assay, Person, and Publication — has at most one Comment per
Comment name. When multiple Comments share a name on the same holder, the store MUST keep the last Comment for that name
(last-wins) and MUST emit a warning log that names the holder kind, holder identity when available, and the duplicated
Comment name. Same Comment names on different holders MUST remain allowed. This normalisation MUST NOT run as part of
HTTP ingest, document-store persist, or `content_hash` computation.

#### Scenario: Duplicate name on one holder is collapsed before Write

- **GIVEN** a parsed ARC whose Investigation has two Comments both named `note` with different values
- **WHEN** the Git store syncs that ARC
- **THEN** `ARC.Write` succeeds
- **AND** only the last `note` value remains on the Investigation
- **AND** a warning is logged for the duplicate Comment name

#### Scenario: Same name on Investigation and Study remains allowed

- **GIVEN** a parsed ARC with Investigation `Comment[RDI]` and Study `Comment[RDI]` with values that may differ
- **WHEN** the Git store syncs that ARC
- **THEN** both Comments remain
- **AND** `ARC.Write` succeeds

#### Scenario: Person and Publication holders are covered

- **GIVEN** a parsed ARC where a Person and a Publication each have two Comments with the same name on that holder
- **WHEN** the Git store syncs that ARC
- **THEN** each holder retains a single Comment for that name (last-wins)
- **AND** `ARC.Write` succeeds
