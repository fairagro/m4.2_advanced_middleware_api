# ARC Store — Delta

## ADDED Requirements

### Requirement: Compact catalog Dataset JSON-LD on worker finalize

When the consolidated backend rebuilds an RDI catalog during **finalize** (Celery
worker), each extracted Schema.org `Dataset` SHALL be JSON-LD-expanded (using
the source document’s `@context`) and then JSON-LD-compacted against a **fixed
target `@context`** that combines:

1. a **version-pinned** schema.org JSON-LD context document, and
2. a pinned ARC/Bioschemas extension term map (at least the ARC Lab/Sample terms
   commonly present in RO-Crate ARC contexts).

The compacted record MUST carry that target `@context` (not the source RO-Crate
context verbatim). Terms unknown to the target context MUST remain as absolute
IRIs after compact. Expand/compact MUST NOT run on the API ingest path. For a
fixed ARC body and the same pinned contexts, two compacted Dataset records MUST
be byte-identical under the catalog’s canonical JSON serialization rules.

#### Scenario: Worker finalize rewrites Dataset context

- **GIVEN** an ARC RO-Crate whose top-level `@context` is an RO-Crate profile
  URL plus ARC/Bioschemas extensions
- **WHEN** catalog finalize rebuilds `{rdi}.json` in the worker
- **THEN** each Dataset’s `@context` is the pinned schema.org + ARC/Bioschemas
  compact context and schema.org properties such as `name` remain short names

#### Scenario: API ingest does not compact

- **GIVEN** a harvest submits an ARC while `consolidated_git` is configured
- **WHEN** the API stores the ARC in CouchDB
- **THEN** the stored ARC body retains its original `@context` and no
  expand/compact is performed at ingest

#### Scenario: Unknown IRIs survive compact

- **GIVEN** a Dataset property whose IRI is not in the pinned schema.org
  context and not in the pinned ARC/Bioschemas map
- **WHEN** the Dataset is compacted during finalize
- **THEN** that property remains as an absolute IRI key or value in the
  catalog record

### Requirement: Load pinned schema.org context once per worker process

The schema.org portion of the compact target MUST come from a **configuration
option** (Pydantic / ConfigWrapper field on the consolidated catalog settings)
that selects a schema.org **release version** (or equivalent immutable pin).
The field MUST have a description and a documented default. Operators MUST be
able to override it via the normal config / environment-variable mechanisms.
The implementation MUST derive the fetch URL from that configured version (e.g.
schema.org `data/releases/<version>/schemaorgcontext.jsonld`) and MUST NOT
hard-code the live unversioned schema.org context as the pin.

The worker MUST fetch that document **at most once per worker process** (eagerly
at process start or lazily before the first compact), reuse the in-memory
document for all Datasets, and MUST NOT re-fetch per Dataset. Concurrent
finalize tasks in the same process MUST share one load without duplicate fetches
or torn reads (safe concurrent initialization). Fetch failure MUST fail finalize
(no silent fallback to RO-Crate passthrough). Changing the configured pin
requires a process restart (or equivalent cache invalidation) before the new
version is used.

#### Scenario: Pin is taken from config

- **GIVEN** consolidated catalog config sets the schema.org context version pin
  (e.g. `30.0`)
- **WHEN** the worker loads the compact target
- **THEN** it fetches the context for that configured version and does not use
  a different hard-coded release

#### Scenario: Single fetch then reuse

- **GIVEN** a worker process with a configured schema.org context pin
- **WHEN** finalize compacts many Datasets for one or more RDIs
- **THEN** the pinned schema.org context is fetched once and reused for every
  compact in that process

#### Scenario: Concurrent first use does not double-fetch

- **GIVEN** two finalize tasks start compact before the schema.org context is
  loaded
- **WHEN** both need the pinned context
- **THEN** exactly one fetch runs and both tasks observe the same loaded
  document
