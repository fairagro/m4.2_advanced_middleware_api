# Catalog Dataset Materialize — Proposal

## Why

Consolidated catalog `{rdi}.json` entries are built by extracting only the root
RO-Crate `Dataset` node, then JSON-LD expand/compact. Referenced entities
(Person, Comment, Study, Assay, license placeholder) remain in the full
`@graph` in CouchDB but appear in the catalog as dangling `@id` references
(for example `creator: {"id": "#Person_Kevin_Urbasch"}`). Downstream consumers
cannot read creator names, comment text, or study/assay metadata without the
full RO-Crate. Schema.org normalization (`catalog-schema-org-jsonld`) fixed
`@context` and term mapping but not reference completeness. This change adds a
materialization step so each catalog entry is a self-contained, schema.org-valid
Dataset record with maximal useful fields.

## What Changes

- Add **`materialize_catalog_dataset()`** on the worker finalize path between
  `extract_catalog_dataset()` and `normalize_catalog_datasets()`.
- Resolve selected references from the source RO-Crate `@graph` into inline
  schema.org-oriented objects (Person, ScholarlyArticle/CreativeWork, nested
  Dataset for Study/Assay, license text/URL).
- Map root-level LDComment metadata to first-class schema.org properties where
  possible (`keywords`, `inLanguage`); use `Comment` only as fallback.
- Strip fragment `@id` values on inlined Person/Comment objects; keep path `@id`
  on `hasPart` children (`studies/…/`, `assays/…/`).
- Missing reference targets: omit property/list entry and log a warning
  (best-effort; do not abort finalize).
- **BREAKING** for published `{rdi}.json` bytes on next finalize (same policy as
  `catalog-schema-org-jsonld`).
- No change to API ingest, CouchDB ARC bodies, harvesters, or ARCtrl.

## Capabilities

### New Capabilities

- _(none)_

### Modified Capabilities

- `arc-store`: Catalog finalize MUST materialize referenced RO-Crate entities
  into each published Dataset before JSON-LD normalize; requirements for inline
  Person/comment/license/hasPart content and handling of missing refs.

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/consolidated_git/`
  (`catalog_serialize.py` or new helper, `store.py` finalize collection).
- Tests: unit tests for materialize + normalize; integration finalize; fixtures
  from `ro_crates/sample.json`, `ro_crates/edaphobase.json`, and synthetic
  dangling-ref cases (no production catalog exports in repo).
- OpenSpec: delta to `openspec/specs/arc-store/spec.md` (extends existing
  catalog JSON-LD requirements from `catalog-schema-org-jsonld` and
  `catalog-jsonld-relative-ids`).
- Ops: next worker finalize rewrites catalog files; no migration job.
