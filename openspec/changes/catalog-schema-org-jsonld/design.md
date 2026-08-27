# Catalog schema.org JSON-LD — Design

## Context

See proposal.md — Why. Today `extract_catalog_dataset` copies the source
RO-Crate `@context` onto each Dataset; finalize runs in the Celery worker
(`finalize_catalog` → `ArcManager.finalize_catalog` → consolidated store
`finalize`). API ingest only stages CouchDB bodies.

Canonical live `https://schema.org/` / `https://schema.org/docs/jsonldcontext.json`
is **not** version-immutable. Schema.org publishes release trees under
`data/releases/<version>/schemaorgcontext.jsonld` (e.g. GitHub
`schemaorg/schemaorg`), which **can** be pinned. Fetch the pinned URL with
`httpx.AsyncClient` (already used elsewhere in the project).

## Goals / Non-Goals

**Goals:**

- Run expand→compact **only on the worker finalize path**.
- Pin a concrete schema.org context **version via config option**; fetch once
  per worker process via `httpx.AsyncClient`; reuse for all Datasets.
- Target context = pinned schema.org document **plus** fixed ARC/Bioschemas map.
- Exploit concurrency for per-Dataset normalize without races on the shared
  context cache.
- Keep catalog byte-stable for fixed ARC set + fixed pin.

**Non-Goals:**

- Expand/compact on API ingest or mutating CouchDB ARC bodies.
- Relying on the unversioned live schema.org context URL as the SoT pin.
- Changing per-ARC `git_repo` / `gitlab_api` backends.
- Full RO-Crate graph reshape into one `@graph` catalog document.

## Decisions

### Decision: Worker-only normalization

**Choice:** Structural Dataset extraction may stay in `catalog_serialize`;
JSON-LD expand/compact runs as part of **consolidated finalize in the Celery
worker** (after Dataset extraction, before `serialize_catalog_file` / Git
write). API mode MUST NOT load schema.org or compact Datasets.

**Why:** Finalize already owns catalog rebuild; keeps ingest fast; matches
operator expectation that Git publish work is worker-side.

**Alternatives:** Compact inside API on each store (rejected—hot path, wrong
process); compact only at serialize with no worker distinction (blurs API vs
worker).

### Decision: Pin schema.org via config option

**Choice:** Add a Pydantic field on consolidated catalog settings (e.g.
`schema_org_context_version` on `ConsolidatedGitConfig` / nested `arc_store`
consolidated settings) with a `description` and a default release (e.g.
`30.0`). ConfigWrapper env/secret overrides apply like other fields. Derive the
immutable fetch URL from that version, e.g. GitHub raw
`…/data/releases/<version>/schemaorgcontext.jsonld`. Compact target merges the
loaded JSON-LD context with the code-constant ARC/Bioschemas extension map. Do
**not** use bare `https://schema.org/` as the pin, and do **not** bury the
version only in code constants without a config knob.

**Why:** Operators must control the pin without a code change; principles require
configurable values on `Config` with descriptions.

**Alternatives:** Vendor full schema.org context in-repo; `@vocab` only; pin
only in `versions.env` without API config (weaker for deployment overlays).

### Decision: One-shot process-local load via httpx

**Choice:** Before the first compact in a worker process, fetch the pinned URL
with `httpx.AsyncClient` (timeouts set explicitly). Cache the parsed context
document in a process-local holder. Subsequent compacts reuse it.
Initialization MUST use a single-flight pattern (`asyncio.Lock` +
double-checked load, or `asyncio.Task` memo) so concurrent finalize tasks do
**not** race into multiple fetches or publish a partially built cache. After
publish, the cached document is treated as **immutable** (read-only sharing).

**Why:** Matches “load once at start / first use, reuse for every Dataset”;
avoids per-Dataset network; safe under Celery concurrency / async gather;
uses the stack already present in the repo.

**Alternatives:** Fetch per Dataset (rejected); blocking sync `requests` on the
event loop (rejected).

### Decision: Source expand contexts (RO-Crate)

**Choice:** Expanding input Datasets still needs RO-Crate (and any other)
remote `@context` URLs from ARC bodies. Resolve those via an offline document
loader backed by **vendored** RO-Crate 1.1/1.2 context files (fail closed on
unknown remotes). Do not network-fetch arbitrary ARC context URLs during
finalize.

**Why:** Expand must be correct and deterministic; RO-Crate contexts are small
and versioned by the URL already present in ARCs.

### Decision: Concurrent Dataset normalize

**Choice:** After the shared context is ready, expand/compact Datasets with
bounded concurrency (`asyncio.TaskGroup` / `gather` + semaphore). Each task
works on its own Dataset dict; no shared mutable JSON-LD state beyond the
read-only cached contexts. Preserve deterministic catalog ordering by sorting
on `@id` **after** normalize (existing serialize contract), not by completion
order.

**Why:** Finalize can touch many ARCs; concurrency helps without races.

### Decision: Breaking catalog bytes is acceptable

**Choice:** Intentional **BREAKING** for published `{rdi}.json`; next finalize
rewrites. No migration job.

## Risks / Trade-offs

- **[Risk] Unversioned schema.org URL drift** → Mitigated by release pin
  (`data/releases/<ver>/schemaorgcontext.jsonld`), not live site context.
- **[Risk] Pin bump changes catalog bytes** → Document; operators bump the
  config field deliberately and restart workers so the process-local cache
  reloads.
- **[Risk] Worker start / first finalize needs network to GitHub (or mirror)**
  → Transient fetch errors → retryable finalize failure; permanent 404/bad pin
  → permanent failure. Optional later: ship a fallback vendored copy of the
  same pin.
- **[Risk] Incomplete ARC/Bioschemas map** → Unknown terms stay absolute IRIs.
- **[Risk] Race on context init** → Single-flight lock/task; immutable cache
  after load.
- **[Trade-off] Catalog bytes change on deploy** → Expected after first
  finalize with the new pin.

## Migration Plan

1. Add pin config + `httpx` fetch + JSON-LD normalize on worker finalize;
   vendor RO-Crate contexts for expand.
2. Deploy workers; first finalize per process fetches pinned schema.org once.
3. Rollback: revert; later finalize restores passthrough for newly built files.
