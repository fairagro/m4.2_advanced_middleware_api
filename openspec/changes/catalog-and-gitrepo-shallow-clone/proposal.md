# Catalog and GitRepo shallow clone — Proposal

## Why

Every `GitContext` clone for ConsolidatedGit catalog finalize and `GitRepo` sync/get
currently pulls the **full** remote history into an ephemeral workdir
([#346](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/346)). Peak
disk, network, and worker time scale with history depth × concurrent Celery workers.
Both backends only need the tip working tree (write/read tip files, commit, push).
Shallow clone (`depth=1`) cuts history transfer without changing observable publish
or sync semantics. Sparse-checkout and in-memory catalog RAM remain out of scope.

## What Changes

- Hardcode `depth=1` on all fresh `GitContext` clones used by ConsolidatedGit and
  `GitRepo` (shared `Repo.clone_from` path).
- No YAML / ConfigWrapper option — depth is fixed for current tip-only usage.
- Keep ephemeral `mkdtemp` + cleanup and existing push / error classification.
- Unit tests that clones pass `depth=1` (and that catalog publish / GitRepo sync
  still succeed against bare remotes).

Non-goals: sparse-checkout; bounding in-memory Dataset/`catalog_bytes` peak (#349);
same-RDI finalize coalescing; `gitlab_api`; operator-tunable clone depth.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Git CLI backends that clone via `GitContext` MUST use a shallow clone
  (`depth=1`) for fresh working copies. Observable catalog bytes and ARC tip content
  MUST remain unchanged vs a full clone for tip-only operations.

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/git_context.py` (primary);
  callers already share this path (`consolidated_git/store.py`, `git_repo/store.py`).
- Tests: GitContext / GitRepo / consolidated publish unit tests asserting shallow
  clone kwargs and tip-only success.
- Specs: `openspec/specs/arc-store/` (new requirement + optional design note).
- Fixes [#346](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/346)
  (scope extended to `GitRepo` as well as catalog finalize).
