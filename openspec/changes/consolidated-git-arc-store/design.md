# Consolidated Git ArcStore — Design

## Context

See `proposal.md` and
[#319](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/319).
Today `ArcStore` implementations (`GitRepo`, deprecated `GitlabApi`) map each
`arc_id` to its own Git project and write an ISA tree. Callers
(`ArcManager.sync_to_gitlab`, harvest completion) must stay backend-agnostic.
Basic middleware already publishes `{rdi}.json` arrays of Schema.org Datasets
into a shared repo ([middleware_repo](https://github.com/fairagro/middleware_repo)).

## Goals / Non-Goals

**Goals:**

- One port (`ArcStore`) with a consolidating implementation + `finalize`.
- Harvest-scoped publish path; **CouchDB dirty-marker staging**; Schema.org
  extraction from RO-Crate; mutually exclusive config.
- **Byte-stable** catalog files for unchanged ARC sets across harvests.
- Documented decisions for issue #319 open questions (below).

**Non-Goals:**

- Dual-write per-ARC GitLab + catalog in one process.
- Basic `openagrar`/`publisso` file-split/jq-merge parity (follow-up).
- Distributed locking against concurrent Basic writers on the same remote.
- Moving content-hash computation into the worker.

## Decisions

### Decision: Keep a single ArcStore port (no CatalogStore)

**Choice:** Add `finalize` to `ArcStore` (default no-op); new
`ConsolidatedGitArcStore` (name illustrative) selected by config.

**Why:** Avoids caller branching; matches issue preferred direction.

**Alternatives:** Separate CatalogStore — rejected.

### Decision: Config shape — mutually exclusive `consolidated_git` key (v1)

**Choice:** Add `consolidated_git: ConsolidatedGitConfig | None` beside
`git_repo` / `gitlab_api`, validated as exactly one set (same pattern as
today). Longer-term `arc_store.type` discriminator MAY replace this without
changing the port.

**Why:** Minimal churn to `Config` / factory / worker config; naming stays
under ArcStore, not a new product noun.

### Decision: Standalone `POST /v3/arcs` → fail-fast 400

**Choice:** When consolidating backend is configured, reject standalone upload.

**Why:** No harvest finalize signal; preferred product cut is harvest-scoped
(issue table). Avoids silent undrained staging.

### Decision: Finalize trigger — async after COMPLETED

**Choice:** `complete_harvest` transitions status to `COMPLETED`, then enqueues
a Celery task that calls `ArcStore.finalize(rdi=…, harvest_id=…)`. HTTP does
not block on Git push. Catalog success/failure uses new events (e.g.
`CATALOG_PUSH_SUCCESS` / `CATALOG_PUSH_FAILED`), distinct from per-ARC
`GIT_PUSH_SUCCESS`.

**Why:** Harvest completion stays responsive; per-ARC backends keep finalize
no-op so the enqueue path is universal. Partial failure (harvest done, catalog
not flushed) is explicit and retriable without reopening the harvest.

**Alternatives:** Sync push inside `complete_harvest` — simpler but risks
timeouts; deferred.

### Decision: Finalize scope — RDI primary, harvest_id contextual

**Choice:** `finalize(rdi=…, harvest_id=…)` rebuilds that RDI’s catalog file.
Rebuild source of truth: **all current CouchDB ARC documents for that RDI**
(not only the completing harvest’s dirty set). Dirty staging optimizes “skip
finalize if nothing changed since last successful publish”; when dirty,
rebuild from full RDI snapshot so overlapping harvests converge.

**Why:** Avoids lost updates when two harvests touch the same RDI; CouchDB
already holds authoritative ARC bodies + content hashes.

### Decision: Staging model — CouchDB dirty markers (not a body dump)

**Choice:** Persist **lightweight dirty markers** in CouchDB (docs or fields
keyed by RDI/`arc_id`) when `create_or_update` runs for **changed** content.
ARC RO-Crate bodies remain the normal ARC documents already stored by the
document store — staging MUST NOT duplicate full crates. An optional cache of
extracted Dataset JSON MAY exist for speed; rebuild from `arc_content` on
finalize is always authoritative. Unchanged content-hash → not dirty.

**Why:** Worker/API restarts must not lose “needs publish”. In-memory staging
is insufficient. CouchDB is already the persistence plane for ARCs and harvest
metadata; a second datastore (Redis, side files) adds ops cost without benefit
for v1. Markers stay small; rebuild reads existing ARC docs.

**Alternatives considered:**

- In-memory dirty set only — rejected (lost on restart).
- Stage full RO-Crate copies in a separate CouchDB collection — rejected
  (duplication, drift vs content-hash documents).
- Rewrite `{rdi}.json` on every ARC — rejected (issue: avoid full-file rewrite
  per ARC).

### Decision: Byte-stable consolidated JSON-LD

**Choice:** For a fixed set of ARC contents for an RDI, two catalog rebuilds
MUST produce **identical file bytes**. That requires at least: deterministic
Dataset array order (sort by `@id`); canonical JSON serialization (sorted
object keys, stable separators/encoding, no insignificant whitespace drift);
no injection of build-time / finalize-time timestamps or other volatile
metadata into the catalog file or commit-driven payload; Dataset extraction
that does not reintroduce order-only noise from nested structures beyond what
the stored ARC already contains (apply the same order-normalization rules as
needed for nested `@id` lists inside extracted Datasets, or serialize from a
canonicalized extract). If nothing is dirty and the remote blob already matches
the freshly built bytes, finalize MUST skip commit/push (no empty “touch”
commits).

**Why:** Operators and git history must not churn on no-op harvests; matches
content-hash stability goals at catalog level.

### Decision: Extraction contract (v1)

**Choice:** From each ARC’s RO-Crate `@graph`, take the Dataset entity that
represents the catalog record (prefer root/`@id` `./` Dataset when present;
otherwise the primary Schema.org `Dataset` node documented in implementation
tests). Emit a JSON array of those objects (each MAY retain its own
`@context` as Basic does). Sort array by Dataset `@id` ascending.

**Why:** Schema.org is already in the RO-Crate; no second upload path.
Exact node selection locked by unit fixtures against sample crates.

### Decision: Basic special cases deferred

**Choice:** v1 writes `{normalized_rdi}.json` only. No `thunen_atlas` split or
publisso jq-merge.

**Why:** Called out as follow-up in #319; keeps first cut shippable.

### Decision: Shared Git plumbing without overloading GitRepo

**Choice:** Reuse `RemoteGitProvider` / clone-commit-push helpers on a
**configured single repo URL** (not `arc_id` as repo path). Do not call
`ARC.WriteAsync` / ISA tree write on this path.

**Why:** Different persistence shape; avoids corrupting per-ARC GitRepo
semantics.

### Decision: Dual-write forbidden; events for catalog flush

**Choice:** Strictly one backend. Staged ARC sync MUST NOT emit
`GIT_PUSH_SUCCESS` as if a per-ARC repo were pushed; emit staging-appropriate
telemetry and catalog flush events on finalize.

### Decision: Coexistence with Basic writers

**Choice:** Configurable remote MAY point at `middleware_repo`. v1 documents
race risk; no lease/lock. Operators SHOULD avoid concurrent Basic+Advanced
writers on the same file set until a follow-up.

## Risks / Trade-offs

- **[Risk] Async finalize lag** → Mitigation: events + metrics; optional
  manual/admin re-finalize task.
- **[Risk] Extraction misses Basic shape** → Mitigation: fixtures from
  middleware_repo samples; adjust extractor behind tests.
- **[Risk] Concurrent harvests / Basic writers** → Mitigation: full-RDI
  rebuild from CouchDB; document no lock in v1.
- **[Risk] Catalog byte drift (key order, timestamps)** → Mitigation: locked
  serializer + unit tests asserting identical bytes for unchanged ARC sets;
  strip/forbid finalize-time fields in the file payload.
- **[Trade-off] Fail-fast standalone arcs** → Forces harvest API for catalog
  deployments; acceptable for preferred product cut.

## Migration Plan

1. Land port `finalize` no-op + config key (disabled).
2. Implement consolidated store + extraction + tests.
3. Wire harvest complete → enqueue finalize; add events.
4. Guard `POST /v3/arcs` when consolidated config active.
5. Roll out on a dedicated remote or isolated branch before sharing
   `middleware_repo` with Basic.
6. Rollback: switch config back to `git_repo`.

## Open Questions

- Exact Dataset node selector details beyond root/`Dataset` (finalize during
  implementation against real OpenAgrar/e!DAL crates).
- Whether empty dirty set skips push vs always rewriting for checksum
  visibility — **decided:** skip push when freshly built bytes equal remote
  blob (see byte-stability decision).
