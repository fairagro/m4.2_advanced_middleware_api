# Catalog schema.org JSON-LD — Proposal

## Why

Consolidated catalog `{rdi}.json` currently copies each ARC’s RO-Crate
`@context` (often `https://w3id.org/ro/crate/1.2/context` plus ARC/Bioschemas
extensions). Downstream consumers expect a schema.org-oriented JSON-LD context.
We need a deterministic expand→compact pass so catalog Datasets compact against
a **vendored** schema.org release context plus a fixed ARC/Bioschemas extension
map, and **emit** the conventional `https://schema.org` IRI (+ extensions). The
work belongs on the **Celery finalize path** (background worker), not on the API
ingest hot path.

## What Changes

- On catalog **finalize** (worker), each extracted Dataset is JSON-LD-**expanded**
  then **compacted** against a target context built from:
  1. a **vendored** schema.org JSON-LD context file in the repo (same approach as
     RO-Crate expand contexts), and
  2. a pinned ARC/Bioschemas extension term map.
- Emitted Dataset `@context` is `["https://schema.org", <extension map>]` (not
  an inline dump of the vendored release, and not the source RO-Crate context).
- Unknown IRIs remain as absolute IRIs after compact.
- **BREAKING** for catalog file bytes vs. RO-Crate context passthrough
  (byte-stability still required for a fixed ARC set + fixed vendored contexts).
- No change to HTTP upload/harvest APIs or CouchDB-stored ARC bodies; API ingest
  does not expand/compact.
- No runtime fetch of schema.org and no config option for the context version;
  upgrading the pin is a deliberate repo file update.

## Capabilities

### New Capabilities

- _(none)_

### Modified Capabilities

- `arc-store`: Catalog Dataset records emitted on finalize MUST use schema.org +
  ARC/Bioschemas compact semantics instead of copying the source RO-Crate
  `@context` unchanged. Normalization runs in the worker finalize path.

## Impact

- Code: consolidated Git finalize / catalog serialization helpers used from the
  Celery worker; offline document loader for RO-Crate expand; concurrent Dataset
  normalization without races.
- Dependency: JSON-LD library (`pyld`) under `api`.
- Artifacts: vendored `jsonld_contexts/` files (RO-Crate 1.1/1.2 + schema.org
  release) packaged with the API wheel.
- Ops: no network dependency for schema.org at finalize; pin bumps are code
  changes that rewrite catalog bytes on the next finalize.
