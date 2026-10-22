# Proposal

## Why

On worker shutdown both Git ArcStores cancel the thread pool and return immediately. An in-flight clone can then miss
its workdir cleanup. Orphan directories are already reclaimed after a 6-hour TTL, so this change only gives a graceful
stop a bounded chance to finish that cleanup, and logs a delete that fails outright.

## What Changes

- On graceful shutdown, wait up to a bound for in-flight pool work so its workdir cleanup can run. Cancel work that has
  not started. After the bound, return and leave any leftover directory to the existing stale-cache reclaim.
- When deleting an ephemeral Git workdir fails, log a warning. Do not fail the Git operation or the shutdown because the
  directory is still there.
- Leave the existing stale-cache reclaim (prefixes, 6-hour TTL, call sites) unchanged. Do not add a periodic sweeper. Do
  not try to clean up after SIGKILL.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `arc-store`: Graceful shutdown MUST wait a bounded time for in-flight Git work, and a failed ephemeral-workdir delete
  MUST be logged.

## Impact

- `middleware/api/src/middleware/api/arc_store/git_repo/store.py` and
  `middleware/api/src/middleware/api/arc_store/consolidated_git/store.py` (executor shutdown and workdir delete).
- Unit tests for shutdown wait and for a logged failed delete.
- `openspec/specs/arc-store/`.
- No HTTP contract change. No change to `openspec/specs/arc-store/` reclaim rules.
