# GitRepo ephemeral workdir — Proposal

## Why

`GitRepo` uses a deterministic local path `cache_dir / arc_id` for clone/write/push/cleanup
([#347](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/347)). With Celery prefork
(`--concurrency>1`) or overlapping thread-pool work, two syncs for the same ARC can corrupt each
other's working tree (`rmtree` / write races). The arc-store design already requires fresh temporary
clones; consolidated catalog finalize already uses unique `mkdtemp` dirs. `GitRepo` does not.

The race is primarily a correctness hardening concern (theoretical under current load), but orphaned
temp dirs after crashes are a real hygiene gap once paths become ephemeral.

## What Changes

- Give each `GitRepo` `_create_or_update` / `_get` invocation a **unique** working directory under
  `cache_dir` (same ephemeral pattern as consolidated finalize).
- Remove the working directory in `finally` after the operation.
- Add lightweight, age-gated orphan cleanup under `cache_dir` for known ephemeral prefixes (and
  legacy `cache_dir / arc_id` leftovers after deploy).
- Optionally share the orphan-sweep helper with consolidated `catalog_finalize_*` dirs.
- Unit/contract tests: unique paths per concurrent invocation; sweep deletes only stale matching
  dirs.

Non-goals: changing `gitlab_api` (legacy, slated for removal); distributed locks; push
deduplication; lowering Celery concurrency as the sole fix; HTTP API contract changes.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: `GitRepo` local Git working copies MUST be unique per invocation (not
  `cache_dir / arc_id`), MUST be removed after use, and the store MUST best-effort reclaim stale
  orphan directories under `cache_dir`.

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/git_repo/store.py`, possibly a small shared
  helper near `git_cli_settings` / arc_store utilities; optional hook from
  `consolidated_git/store.py`.
- Tests: GitRepo unit tests for path uniqueness / cleanup; orphan-sweep unit tests.
- Specs: `openspec/specs/arc-store/` (requirement + design decision 3 made concrete).
- Fixes [#347](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/347).
- Branch: `fix/gitrepo-ephemeral-workdir` (off current `main`).
