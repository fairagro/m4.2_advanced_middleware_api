# Catalog schema.org JSON-LD — Proposal

## Why

Consolidated catalog `{rdi}.json` currently copies each ARC’s RO-Crate
`@context` (often `https://w3id.org/ro/crate/1.2/context` plus ARC/Bioschemas
extensions). Downstream consumers expect a schema.org-oriented JSON-LD context.
We need a deterministic expand→compact pass so catalog Datasets use a **pinned
schema.org context** plus a fixed ARC/Bioschemas extension map. The work belongs
on the **Celery finalize path** (background worker), not on the API ingest hot
path.

## What Changes

- On catalog **finalize** (worker), each extracted Dataset is JSON-LD-**expanded**
  then **compacted** against a target context built from:
  1. a **version-pinned** schema.org JSON-LD context selected by a **config
     option** (loaded once per worker process), and
  2. a pinned ARC/Bioschemas extension term map.
- Unknown IRIs remain as absolute IRIs after compact.
- **BREAKING** for catalog file bytes vs. RO-Crate context passthrough
  (byte-stability still required for a fixed ARC set + fixed pinned contexts).
- No change to HTTP upload/harvest APIs or CouchDB-stored ARC bodies; API ingest
  does not expand/compact.

## Capabilities

### New Capabilities

- _(none)_

### Modified Capabilities

- `arc-store`: Catalog Dataset records emitted on finalize MUST use the pinned
  schema.org + ARC/Bioschemas compact context instead of copying the source
  RO-Crate `@context` unchanged. Normalization runs in the worker finalize path.

## Impact

- Code: consolidated Git finalize / catalog serialization helpers used from the
  **Celery worker**; process-local context cache; concurrent Dataset
  normalization without races.
- Dependency: JSON-LD library (e.g. `pyld`) under `api`; async HTTP fetch of the
  pinned schema.org context via `httpx.AsyncClient`.
- Config: **required config option** for the schema.org release/version pin
  (ConfigWrapper / Pydantic field on consolidated catalog settings; env override
  supported like other config).
- Ops: first finalize after deploy may fetch the pinned context once per worker
  process; subsequent Datasets reuse the in-memory copy.
