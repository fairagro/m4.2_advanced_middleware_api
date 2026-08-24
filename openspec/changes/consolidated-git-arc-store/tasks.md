# Consolidated Git ArcStore — Tasks

## 1. Port and configuration

- [ ] 1.1 Add `ArcStore.finalize(rdi=…, harvest_id=…)` with default successful
      no-op on `GitRepo` and `GitlabApi`; cover with unit tests
- [ ] 1.2 Add `ConsolidatedGitConfig` and mutually exclusive
      `consolidated_git` on API/worker `Config` (exactly one of `git_repo` /
      `gitlab_api` / `consolidated_git`); wire factory selection
- [ ] 1.3 Update Spec-to-Code mapping / `AGENTS.md` for the new implementation
      module path

## 2. Consolidated store implementation

- [ ] 2.1 Implement durable **CouchDB dirty markers** keyed by RDI/`arc_id`
      (markers only — no second RO-Crate dump); mark dirty only when content
      changed; skip dirty on unchanged hash
- [ ] 2.2 Implement Schema.org `Dataset` extraction from RO-Crate `@graph`
      (root/`Dataset` rule) with unit fixtures
- [ ] 2.3 Implement `finalize`: rebuild `{rdi}.json` with **byte-stable**
      serialization (sort Datasets by `@id`, sorted JSON keys, no build-time
      timestamps) from CouchDB ARCs for that RDI; skip commit/push when bytes
      match remote; clear dirty markers after success
- [ ] 2.4 Map transient vs permanent Git/extraction failures to existing
      `ArcStoreTransientError` / `ArcStoreError` conventions; health check
      for consolidated remote

## 3. Orchestration and HTTP guards

- [ ] 3.1 On harvest `COMPLETED`, enqueue Celery finalize task; keep status
      transition non-blocking on Git push; invoke finalize for all backends
      (no-op on per-ARC stores)
- [ ] 3.2 Add catalog flush success/failure events (distinct from
      `GIT_PUSH_SUCCESS`); ensure staged `create_or_update` does not emit
      false per-ARC push success
- [ ] 3.3 When `consolidated_git` is configured, reject `POST /v3/arcs` with
      HTTP `400` before sync scheduling

## 4. Tests and docs

- [ ] 4.1 Unit tests: dirty markers, extraction, byte-identical rebuild for
      unchanged ARC sets, finalize publish/skip, finalize no-op, config
      mutual exclusivity, standalone reject, harvest enqueue
- [ ] 4.2 Optional: integration test against a temporary git remote
- [ ] 4.3 Document operator notes: no dual-write; race risk if sharing
      Basic’s remote; v1 file naming `{rdi}.json` only (no openagrar splits)
- [ ] 4.4 Run focused `uv run pytest` for arc_store / harvest / arcs suites;
      `uv run ruff check/format --config pyproject.toml` on touched code
