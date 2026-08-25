# Consolidated Git ArcStore — Design

## Context

See `proposal.md` and
[#319](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/319).
Today `ArcStore` implementations (`GitRepo`, deprecated `GitlabApi`) map each
`arc_id` to its own Git project and write an ISA tree. Callers
(`ArcManager.sync_to_gitlab`, harvest completion) must stay backend-agnostic.
Basic middleware already publishes `{rdi}.json` arrays of Schema.org Datasets
into a shared repo ([middleware_repo](https://github.com/fairagro/middleware_repo))
— Advanced will emit the **same file shape**, but to a **separately configured**
remote (not Basic’s repo).

Today’s API path already separates **CouchDB ingest** (always) from **Git
persist** (Celery only when content is new/changed). For the consolidated
catalog, Git persist is a **full RDI file**, so the natural hook is harvest
completion — not a per-ARC worker task.

## Goals / Non-Goals

**Goals:**

- One port (`ArcStore`) with a consolidating implementation + `finalize(rdi=…)`.
- Harvest-scoped publish: CouchDB holds ARC bodies; finalize rebuilds the
  catalog once per completed harvest.
- **Byte-stable** catalog files for unchanged ARC sets across harvests.
- Config selects backend via `arc_store.type` (preferred) while keeping legacy
  top-level keys working but marked obsolete; no caller `if catalog else …`
  branching.
- Documented answers for issue #319 open questions (section below).

**Non-Goals:**

- CouchDB dirty-marker documents (redundant with content-hash + byte compare).
- Per-ARC Celery Git sync when the consolidated backend is configured.
- Dual-write per-ARC GitLab + catalog in one process.
- Basic `openagrar`/`publisso` file-split/jq-merge parity (follow-up).
- Sharing Basic’s `middleware_repo` remote or distributed locking against
  Basic writers.
- Moving content-hash computation into the worker.

## Answers to issue #319 open questions

Explicit decisions for the numbered open questions in
[#319](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/319):

| # | Question (issue) | Decision |
| --- | --- | --- |
| **1** | Standalone `POST /v3/arcs` when consolidating store is configured? | **Reject with HTTP 400.** No silent staging, no debounce, no eager per-ARC rewrite. Harvest-scoped product cut. |
| **2** | Finalize trigger and HTTP semantics? | Mark harvest **`COMPLETED` first**, then **enqueue** async Celery finalize. HTTP MUST NOT wait for Git push. On **permanent** catalog push failure: harvest stays `COMPLETED`; record `CATALOG_PUSH_FAILED`. On **transient** failure: do **not** append `CATALOG_PUSH_FAILED` before Celery retry (same as per-ARC `GIT_PUSH_*`); finalize MAY be retried without re-opening the harvest. |
| **3** | Finalize scope: `rdi` vs `harvest_id` vs both? Overlapping harvests? | **`finalize(rdi=…)` only.** CouchDB stores the **latest** ARC body per `arc_id`, not a harvest-scoped snapshot, so `harvest_id` cannot select “ARCs of that harvest” for a rebuild. Rebuild from **all** current ARC documents for the RDI. Overlapping harvests converge on CouchDB; **last successful push** wins on the remote. A Celery task MAY still *carry* `harvest_id` for logging/correlation; it is not an ArcStore finalize argument. |
| **4** | Staging model vs CouchDB / content-hash? | **No dirty-marker documents.** Staging = normal CouchDB ARC documents. Content-hash still gates CouchDB writes (unchanged ARC → no doc update). Optional: skip finalize **enqueue** when harvest stats show `arcs_new + arcs_updated == 0`. When finalize runs, **byte equality** vs remote file skips commit/push. |
| **5** | Extraction contract for Basic-like output? *(clarified below)* | Prefer root Dataset (`@id` `./`); else first `@graph` node typed as Schema.org `Dataset`. Emit a **JSON array** of those objects; each MAY keep its own `@context`. Order Datasets by `@id`; serialize with sorted object keys and stable separators (**byte-stable**). No finalize-/build-time timestamps injected into the payload. |
| **6** | Basic special cases (`openagrar` / `publisso`)? | **Deferred.** v1 writes `{rdi}.json` only (one file per configured RDI name). |
| **7** | Target repository & coexistence with Basic? | Catalog remote **MUST be configurable**. Advanced **will not** use Basic’s `middleware_repo` as the production target. Coexistence/locking against Basic writers is out of scope for v1. |
| **8** | Config shape / naming? | Prefer **`arc_store.type`** discriminator (`git_repo` \| `gitlab_api` \| `consolidated_git`) with nested settings. **Legacy top-level** `git_repo` / `gitlab_api` (and any transitional `consolidated_git` top-level) MUST keep working and be marked **obsolete/deprecated** with a migration path to `arc_store`. Naming stays under ArcStore (no second product noun). |
| **9** | Dual-write? | **Strictly one backend** per deployment. Never per-ARC GitLab projects and consolidated catalog in the same process. |
| **10** | Success events / metrics? | Catalog flush: `CATALOG_PUSH_SUCCESS` / `CATALOG_PUSH_FAILED`. MUST NOT emit per-ARC `GIT_PUSH_SUCCESS` for this backend. “ARC stored only” = CouchDB ingest with **no** catalog event until finalize. |

### Clarification: what question 5 is asking

Issue #319 asks how we turn a full ARC RO-Crate (large `@graph` with many
node types) into the **small Schema.org records** Basic puts in `{rdi}.json`.
Concrete sub-questions:

1. Which `@graph` node is the catalog Dataset (root `./`? first `Dataset`?
   DOI-bearing node?)?
2. Is the file a JSON **array of objects** (Basic style, possibly each with
   `@context`) or a reshaped single graph?
3. How do we order the array so two harvests with the same ARC set do not
   produce noisy Git diffs?

The table row for #5 locks those choices for v1. Fine-tuning the Dataset
selector against real OpenAgrar/e!DAL crates MAY adjust the extractor behind
tests without changing the array / byte-stability contract.

## Decisions

### Decision: Keep a single ArcStore port (no CatalogStore)

**Choice:** Add `finalize` to `ArcStore` (default no-op); new
`ConsolidatedGitArcStore` (name illustrative) selected by config.

**Why:** Avoids caller branching; matches issue preferred direction.

**Alternatives:** Separate CatalogStore — rejected.

### Decision: No dirty markers — CouchDB bodies are the staging area

**Choice:** Do **not** introduce catalog dirty-marker documents. Authoritative
ARC RO-Crate bodies remain the normal document-store ARC documents (updated
only when content-hash says new/changed). `finalize` always rebuilds
`{rdi}.json` from **all** current ARC documents for that RDI.

**Why:** Finalize must write the full catalog anyway. Change detection already
happens at CouchDB ingest. Extra markers duplicate that signal and add failure
modes. Skip useless Git work via **byte equality** against the remote file
(and optionally skip enqueue when harvest stats show `arcs_new + arcs_updated
== 0`).

**Alternatives considered:**

- Dirty markers on per-ARC Celery sync — rejected (redundant; wrong grain).
- Rewrite `{rdi}.json` on every changed ARC — rejected (N full-file rewrites
  per harvest; issue prefers deferred publish).
- `finalize(harvest_id=…)` selecting harvest-scoped ARCs — rejected: CouchDB
  keeps only the latest ARC body, not per-harvest snapshots.

### Decision: Pipeline — no per-ARC Git Celery task for consolidated backend

**Choice:** When the consolidated backend is configured:

1. Harvest ARC submit → CouchDB only (existing path); **do not**
   `dispatch_sync_arc` / per-ARC `create_or_update` Git work.
2. Harvest → `COMPLETED` → enqueue **one** Celery task that calls
   `finalize(rdi=…)`.
3. Finalize loads all RDI ARCs from CouchDB, extracts Datasets, serializes
   byte-stable JSON, push if remote differs.

`ArcStore.create_or_update` on the consolidating backend is unused for the
happy path (or remains a no-op / unsupported for callers that wrongly invoke
it). Per-ARC backends keep today’s queue-on-change behaviour.

**Why:** Aligns “background work only when needed” with catalog semantics:
needed work is one catalog publish per harvest, not N Git projects.

### Decision: Config shape — `arc_store.type` preferred; legacy keys obsolete

**Choice:** Introduce `arc_store` with a `type` discriminator
(`git_repo` | `gitlab_api` | `consolidated_git`) and nested backend settings.
Keep existing top-level `git_repo` / `gitlab_api` (and transitional top-level
`consolidated_git` if present during migration) **working** but mark them
**obsolete/deprecated** in docs and preferably via Pydantic/config warnings.
Validation: exactly one effective backend (from `arc_store` **or** a single
legacy top-level key), never dual-write.

**Why:** Matches operator wish for an explicit store type while preserving
backward-compatible deployments and Helm/env overlays that still set top-level
keys.

### Decision: Standalone `POST /v3/arcs` → fail-fast 400

**Choice:** When consolidating backend is configured, reject standalone upload.

**Why:** No harvest finalize signal; preferred product cut is harvest-scoped
(issue table).

### Decision: Finalize trigger — async after COMPLETED

**Choice:** Status → `COMPLETED`, then enqueue finalize. HTTP does not block on
Git push. Catalog success/failure uses `CATALOG_PUSH_SUCCESS` /
`CATALOG_PUSH_FAILED` (not per-ARC `GIT_PUSH_*`). Optional optimization: skip
enqueue when harvest statistics show no new/updated ARCs (unchanged-only
harvest); byte compare still protects no-op pushes if finalize runs.

**Why:** Harvest completion stays responsive; per-ARC backends keep finalize
no-op so the enqueue path can stay universal if desired.

### Decision: Finalize scope — RDI only

**Choice:** `ArcStore.finalize(rdi=…)` rebuilds that RDI’s catalog from **all**
CouchDB ARC documents for the RDI. No `harvest_id` parameter on the port.

**Why:** Document store holds latest ARC content only; harvest cannot be used
as a filter for which bodies enter `{rdi}.json`. Overlapping harvests converge
on CouchDB (last successful push wins on the remote). Worker payloads MAY
include `harvest_id` solely for observability.

### Decision: Byte-stable consolidated JSON-LD

**Choice:** For a fixed set of ARC contents for an RDI, two catalog rebuilds
MUST produce **identical file bytes**: Dataset array sorted by `@id`;
canonical JSON (sorted object keys, stable separators); no finalize-/build-time
timestamps in the payload. If remote blob already equals freshly built bytes,
skip commit/push.

### Decision: Extraction contract (v1)

**Choice:** From each ARC’s RO-Crate `@graph`, take the Dataset entity that
represents the catalog record (prefer root/`@id` `./` Dataset when present;
otherwise the primary Schema.org `Dataset` node locked by tests). Emit a JSON
array of those objects (each MAY retain its own `@context` as Basic does).

### Decision: Basic special cases deferred

**Choice:** v1 writes `{rdi}.json` only. No `thunen_atlas` split or
publisso jq-merge.

### Decision: Shared Git plumbing without overloading GitRepo

**Choice:** Reuse `GitContext` / clone-commit-push on the **configured catalog
remote URL** (one shared remote, not one repo per `arc_id`). Do not call
`ARC.WriteAsync`. Each finalize Git operation uses its **own ephemeral local
working directory** (see concurrency decision below), not a process-wide shared
clone cache.

**Why:** Same remote as Basic’s catalog model; isolate Git I/O from per-ARC
`GitRepo` ISA writes without duplicating low-level Git helpers.

### Decision: Ephemeral Git working copy per finalize (no shared local clone)

**Choice:** Mirror the existing `GitRepo` lifecycle: clone (or init) into a
**dedicated temporary directory for this operation**, commit/push, then
**always delete** the directory in a `finally` block (e.g.
`tempfile.mkdtemp` under `cache_dir`, or equivalent unique path).

- **Do not** keep a stable `local_clone_path()` reused across concurrent
  finalize tasks (that would race across Celery worker processes and thread-
  pool workers on the same host).
- **Do** follow the same cleanup discipline as `GitRepo._create_or_update`,
  which removes `cache_dir / arc_id` after each sync even though the path
  name is deterministic per ARC.
- For consolidated finalize, the temp dir MUST be **unique per invocation**
  (e.g. include a random suffix), because many tasks target the **same**
  catalog remote and `{rdi}.json`.

**Why:** Eliminates filesystem/git-index races on the worker host without
distributed locks. Parallel finalizes remain safe locally; the shared remote
still follows last-successful-push semantics (see below).

**Alternatives considered:**

- Stable shared clone + file lock — rejected (extra infra; diverges from
  `GitRepo` pattern).
- Celery `concurrency=1` for finalize only — rejected as the sole fix (API
  replicas / thread pool could still overlap; ephemeral dirs are simpler).

### Decision: Dual-write forbidden; events for catalog flush

**Choice:** Strictly one backend. No false `GIT_PUSH_SUCCESS` for catalog
deployments; catalog flush events on finalize only.

### Decision: Separate configurable catalog remote (not Basic’s repo)

**Choice:** Operators MUST configure the catalog Git URL/credentials. Production
Advanced deployments use their **own** remote — not Basic’s
`middleware_repo`. v1 does not implement distributed locking on the remote;
concurrent pushes to the same branch rely on Git fetch/reset at operation
start and Celery retry on transient push failures.

## Concurrency & thread safety

### CouchDB ingest (API)

- Parallel harvest ARC submissions for **different** `arc_id` values are safe:
  each ARC is its own document with optimistic-concurrency retries
  (`save_document`).
- The same `arc_id` concurrent updates are serialized by CouchDB `_rev`
  conflicts and retry logic.
- **Gap (existing API, not introduced by this change):**
  `POST /v3/harvests/{id}/arcs` does not yet require `status == RUNNING`, so
  ARCs could land after `COMPLETED` while finalize is queued. Mitigation for
  v1: finalize reads **current** CouchDB state; a later finalize or retry
  converges. Optional follow-up: reject non-`RUNNING` harvest submits with
  `409`.

### Finalize read → push window

- `list_arc_contents_by_rdi` is a **point-in-time** paginated scan, not a
  snapshot transaction. Ingest concurrent with finalize can produce a catalog
  file that omits the last millisecond of writes; the next successful finalize
  fixes it. Acceptable under eventual-consistency semantics.

### Parallel finalize tasks (same RDI or different RDIs)

| Layer | Behaviour |
| ----- | --------- |
| **Local worker filesystem** | Safe when each finalize uses an **ephemeral** temp clone and deletes it afterward (no shared working tree). |
| **Git remote** | Multiple workers may push to the same catalog repo/branch. Each operation: fresh clone → fetch/reset → write `{rdi}.json` → commit → push. **Last successful push wins** on the remote; an earlier push based on a stale CouchDB read may be overwritten by a later finalize — consistent with “CouchDB is source of truth”. |
| **Push conflicts** | Interleaved pushes may surface as transient Git errors (non-fast-forward, remote changed during operation). Classify as `ArcStoreTransientError`; Celery retry re-clones from remote and rebuilds from CouchDB. |

No distributed lock is required for v1 given ephemeral local clones + retry.

### Thread pool / Celery

- `ConsolidatedGitArcStore` runs blocking Git work in a thread-pool executor
  (same pattern as `GitRepo`). Ephemeral dirs make concurrent executor tasks
  independent on disk.
- Celery prefork: multiple worker **processes** may run finalize concurrently;
  ephemeral dirs avoid cross-process clone corruption.

### Reference: existing `GitRepo` pattern

`GitRepo._create_or_update` uses `GitContext` with `local_path =
cache_dir / arc_id`, then **`shutil.rmtree(local_path)` in `finally`** after
each operation. Consolidated finalize follows the same **clone → work → delete**
discipline, but MUST use a **unique** directory per invocation because all
catalog tasks share one remote (not one path per `arc_id`).

## Risks / Trade-offs

- **[Risk] Async finalize lag** → Mitigation: events + metrics; optional
  re-finalize task.
- **[Risk] Extraction misses Basic shape** → Mitigation: fixtures; adjust
  extractor behind tests.
- **[Risk] Concurrent harvests / parallel finalize** → Mitigation: ephemeral
  local clones (no shared working tree); full-RDI rebuild from CouchDB; last
  successful remote push wins; transient Git errors retried.
- **[Risk] Catalog byte drift** → Mitigation: locked serializer + identical-byte
  tests.
- **[Risk] Finalize snapshot vs late ingest** → Mitigation: eventual
  consistency; optional follow-up harvest `RUNNING` guard on ARC submit.
- **[Trade-off] Fail-fast standalone arcs** → Forces harvest API for catalog
  deployments; acceptable for preferred product cut.
- **[Trade-off] Finalize always rebuilds full RDI** → Simpler and correct;
  cost accepted vs dirty-marker complexity.
- **[Trade-off] Dual config shapes** → Legacy top-level keys + `arc_store.type`
  need clear deprecation docs to avoid operator confusion.
- **[Trade-off] Ephemeral clone per finalize** → Extra clone/fetch cost vs a
  long-lived cache; accepted for correctness and parity with `GitRepo` cleanup.

## Migration Plan

1. Land port `finalize(rdi=…)` no-op + config (`arc_store.type` + obsolete
   legacy keys).
2. Implement consolidated store + extraction + list-by-RDI + tests.
3. Skip per-ARC sync dispatch when consolidated; harvest complete → finalize.
4. Guard `POST /v3/arcs` when consolidated config active.
5. Roll out against the **Advanced-owned** catalog remote.
6. Rollback: switch config back to `git_repo` (legacy or `arc_store.type`).

## Open Questions

- Exact Dataset node selector details beyond root/`Dataset` (finalize during
  implementation against real OpenAgrar/e!DAL crates).
- Whether to skip finalize enqueue when harvest stats show zero new/updated
  ARCs (optional optimization; byte compare remains mandatory when finalize
  runs).
- Deprecation UX details for legacy top-level keys (warning log vs config
  validation message vs both).
