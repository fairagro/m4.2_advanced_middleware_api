# Catalog schema.org JSON-LD — Design

## Context

See proposal.md — Why. Today `extract_catalog_dataset` copies the source
RO-Crate `@context` onto each Dataset; finalize runs in the Celery worker
(`finalize_catalog` → `ArcManager.finalize_catalog` → consolidated store
`finalize`). API ingest only stages CouchDB bodies.

Canonical live `https://schema.org/` is **not** version-immutable. Schema.org
publishes release trees under `data/releases/<version>/schemaorgcontext.jsonld`.
We **vendor** a chosen release file in-repo (like RO-Crate contexts) and use it
only as the pyld compact input. Published Dataset `@context` uses the
conventional public IRI `https://schema.org` plus ARC/Bioschemas extensions.

## Goals / Non-Goals

**Goals:**

- Run expand→compact **only on the worker finalize path**.
- Compact against a **vendored** schema.org release document plus fixed
  ARC/Bioschemas map; emit `@context` as `https://schema.org` + that map.
- Exploit concurrency for per-Dataset normalize without races on shared
  read-only contexts.
- Keep catalog byte-stable for fixed ARC set + fixed vendored pin.

**Non-Goals:**

- Expand/compact on API ingest or mutating CouchDB ARC bodies.
- Runtime HTTP fetch of schema.org (or a config option for the release version).
- Changing per-ARC `git_repo` / `gitlab_api` backends.
- Full RO-Crate graph reshape into one `@graph` catalog document.

## Decisions

### Decision: Worker-only normalization

**Choice:** Structural Dataset extraction may stay in `catalog_serialize`;
JSON-LD expand/compact runs as part of **consolidated finalize in the Celery
worker** (after Dataset extraction, before `serialize_catalog_file` / Git
write). API mode MUST NOT compact Datasets.

**Why:** Finalize already owns catalog rebuild; keeps ingest fast; matches
operator expectation that Git publish work is worker-side.

**Alternatives:** Compact inside API on each store (rejected—hot path, wrong
process); compact only at serialize with no worker distinction (blurs API vs
worker).

### Decision: Vendor schema.org release (no config pin / no fetch)

**Choice:** Ship `schemaorg-<version>-context.jsonld` under
`arc_store/jsonld_contexts/` (initially release `30.0`). Load it offline for
pyld compact, merged with the code-constant ARC/Bioschemas extension map.
Published Dataset `@context` MUST be
`["https://schema.org", <extension map>]` — not the GitHub release URL and not
an inline dump of the release file. Do **not** add a ConfigWrapper field for the
schema.org version; bumping the pin is a deliberate file (+ code comment)
change.

**Why:** Same offline/deterministic model as RO-Crate expand contexts; no
worker network dependency; no deploy-time config drift. Emitting
`https://schema.org` matches common Schema.org JSON-LD practice and avoids N×
inline context bloat in the catalog array.

**Alternatives:** Fetch pinned release via httpx + config version (rejected—
ops complexity, network); emit release URL or inline map (rejected—uncommon /
oversized); use live `https://schema.org` as compact input (rejected—
non-deterministic).

### Decision: Source expand contexts (RO-Crate)

**Choice:** Expanding input Datasets still needs RO-Crate (and any other)
remote `@context` URLs from ARC bodies. Resolve those via an offline document
loader backed by **vendored** RO-Crate 1.1/1.2 context files (fail closed on
unknown remotes). Do not network-fetch arbitrary ARC context URLs during
finalize.

**Why:** Expand must be correct and deterministic; RO-Crate contexts are
versioned by the URL already present in ARCs.

### Decision: Concurrent Dataset normalize

**Choice:** Expand/compact Datasets with bounded concurrency
(`asyncio.TaskGroup` / `gather` + semaphore). Each task works on its own
Dataset dict; no shared mutable JSON-LD state beyond the read-only vendored
contexts. Preserve deterministic catalog ordering by sorting on `@id` **after**
normalize (existing serialize contract), not by completion order.

**Why:** Finalize can touch many ARCs; concurrency helps without races.

### Decision: Breaking catalog bytes is acceptable

**Choice:** Intentional **BREAKING** for published `{rdi}.json`; next finalize
rewrites. No migration job.

## Risks / Trade-offs

- **[Risk] Vendored pin goes stale** → Document bump procedure (replace file +
  rename/version comment); next finalize rewrites catalogs.
- **[Risk] Incomplete ARC/Bioschemas map** → Unknown terms stay absolute IRIs.
- **[Trade-off] Catalog bytes change on pin bump** → Expected after deploy +
  finalize.
- **[Trade-off] Emitted `https://schema.org` vs compact pin** → Readers that
  re-expand against a different live schema.org may diverge slightly; accepted
  for Interop. Compact term choice remains pinned by the vendored file.

## Migration Plan

1. Vendor schema.org + RO-Crate contexts; JSON-LD normalize on worker finalize.
2. Deploy workers; finalize rewrites `{rdi}.json` offline.
3. Rollback: revert; later finalize restores prior behaviour for newly built
   files.
