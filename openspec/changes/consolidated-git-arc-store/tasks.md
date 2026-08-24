# Consolidated Git ArcStore — Tasks

## 1. Port and configuration

- [x] 1.1 Add `ArcStore.finalize(rdi=…)` with default successful no-op on
      `GitRepo` and `GitlabApi`; cover with unit tests
- [x] 1.2 Add `ConsolidatedGitConfig` and preferred `arc_store.type`
      discriminator (`git_repo` | `gitlab_api` | `consolidated_git`); keep
      legacy top-level `git_repo` / `gitlab_api` / transitional
      `consolidated_git` working but marked obsolete; exactly one effective
      backend; wire factory selection
- [x] 1.3 Update Spec-to-Code mapping / `AGENTS.md` for the new implementation
      module path

## 2. Consolidated store implementation

- [x] 2.1 Add document-store support to list ARC contents by RDI (for finalize
      rebuild); no dirty-marker documents
- [x] 2.2 Implement Schema.org `Dataset` extraction from RO-Crate `@graph`
      (root/`Dataset` rule) with unit fixtures
- [x] 2.3 Implement `finalize`: rebuild `{rdi}.json` with **byte-stable**
      serialization (sort Datasets by `@id`, sorted JSON keys, no build-time
      timestamps) from all CouchDB ARCs for that RDI; skip commit/push when
      bytes match remote
- [x] 2.4 Git publish via **ephemeral per-operation clone** (unique temp dir
      under `cache_dir`, `GitContext` clone → write → commit/push →
      `shutil.rmtree` in `finally` — same lifecycle as `GitRepo`, no stable
      shared local clone path); map transient vs permanent Git/extraction
      failures to `ArcStoreTransientError` / `ArcStoreError`; health check
      for consolidated remote

## 3. Orchestration and HTTP guards

- [x] 3.1 When consolidated backend is configured, do **not** dispatch per-ARC
      Git sync on ARC ingest; on harvest `COMPLETED`, enqueue Celery finalize
      for `rdi` (optional skip when stats show zero new/updated)
- [x] 3.2 Add catalog flush success/failure events (distinct from
      `GIT_PUSH_SUCCESS`); never emit false per-ARC push success for this
      backend
- [x] 3.3 When consolidated backend is configured, reject `POST /v3/arcs` with
      HTTP `400` before sync scheduling

## 4. Tests and docs

- [x] 4.1 Unit tests: extraction, byte-identical rebuild for unchanged ARC
      sets, finalize publish/skip, finalize no-op, ephemeral clone cleanup
      (temp dir removed after success and failure), no per-ARC sync dispatch,
      config mutual exclusivity / `arc_store.type` + obsolete legacy keys,
      standalone reject, harvest enqueue
- [x] 4.2 Optional: integration test against a temporary git remote
- [x] 4.3 Document operator notes: no dual-write; Advanced-owned catalog
      remote (not Basic’s `middleware_repo`); v1 file naming `{rdi}.json`
      only (no openagrar splits); CouchDB bodies are the catalog source (no
      dirty markers); migrate to `arc_store.type`
- [x] 4.4 Run focused `uv run pytest` for arc_store / harvest / arcs suites;
      `uv run ruff check/format --config pyproject.toml` on touched code
