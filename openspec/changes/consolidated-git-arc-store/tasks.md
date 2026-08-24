# Consolidated Git ArcStore — Tasks

## 1. Port and configuration

- [ ] 1.1 Add `ArcStore.finalize(rdi=…)` with default successful no-op on
      `GitRepo` and `GitlabApi`; cover with unit tests
- [ ] 1.2 Add `ConsolidatedGitConfig` and preferred `arc_store.type`
      discriminator (`git_repo` | `gitlab_api` | `consolidated_git`); keep
      legacy top-level `git_repo` / `gitlab_api` / transitional
      `consolidated_git` working but marked obsolete; exactly one effective
      backend; wire factory selection
- [ ] 1.3 Update Spec-to-Code mapping / `AGENTS.md` for the new implementation
      module path

## 2. Consolidated store implementation

- [ ] 2.1 Add document-store support to list ARC contents by RDI (for finalize
      rebuild); no dirty-marker documents
- [ ] 2.2 Implement Schema.org `Dataset` extraction from RO-Crate `@graph`
      (root/`Dataset` rule) with unit fixtures
- [ ] 2.3 Implement `finalize`: rebuild `{rdi}.json` with **byte-stable**
      serialization (sort Datasets by `@id`, sorted JSON keys, no build-time
      timestamps) from all CouchDB ARCs for that RDI; skip commit/push when
      bytes match remote
- [ ] 2.4 Git publish via **ephemeral per-operation clone** (unique temp dir
      under `cache_dir`, `GitContext` clone → write → commit/push →
      `shutil.rmtree` in `finally` — same lifecycle as `GitRepo`, no stable
      shared local clone path); map transient vs permanent Git/extraction
      failures to `ArcStoreTransientError` / `ArcStoreError`; health check
      for consolidated remote

## 3. Orchestration and HTTP guards

- [ ] 3.1 When consolidated backend is configured, do **not** dispatch per-ARC
      Git sync on ARC ingest; on harvest `COMPLETED`, enqueue Celery finalize
      for `rdi` (optional skip when stats show zero new/updated)
- [ ] 3.2 Add catalog flush success/failure events (distinct from
      `GIT_PUSH_SUCCESS`); never emit false per-ARC push success for this
      backend
- [ ] 3.3 When consolidated backend is configured, reject `POST /v3/arcs` with
      HTTP `400` before sync scheduling

## 4. Tests and docs

- [ ] 4.1 Unit tests: extraction, byte-identical rebuild for unchanged ARC
      sets, finalize publish/skip, finalize no-op, ephemeral clone cleanup
      (temp dir removed after success and failure), no per-ARC sync dispatch,
      config mutual exclusivity / `arc_store.type` + obsolete legacy keys,
      standalone reject, harvest enqueue
- [ ] 4.2 Optional: integration test against a temporary git remote
- [ ] 4.3 Document operator notes: no dual-write; Advanced-owned catalog
      remote (not Basic’s `middleware_repo`); v1 file naming `{rdi}.json`
      only (no openagrar splits); CouchDB bodies are the catalog source (no
      dirty markers); migrate to `arc_store.type`
- [ ] 4.4 Run focused `uv run pytest` for arc_store / harvest / arcs suites;
      `uv run ruff check/format --config pyproject.toml` on touched code
