# ARC Store — Delta

## ADDED Requirements

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
