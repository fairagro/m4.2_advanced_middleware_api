# Tasks

## 1. Bounded executor shutdown

- [ ] 1.1 Add a helper that cancels unstarted executor work and waits at most 60 seconds for work that has started, and
      verify a unit test that a fast task is finished before the helper returns, a task that outlasts the bound does not
      delay the return past the bound, and a task that has not started does not run
- [ ] 1.2 Call that helper from `GitRepo.shutdown` and `ConsolidatedGitArcStore.shutdown`, and verify a unit test that
      each shutdown returns when in-flight work exceeds the bound

## 2. Logged workdir delete

- [ ] 2.1 Delete ephemeral Git workdirs through one helper that logs a warning with the path on `OSError` and does not
      raise, use it from `GitRepo` and catalog publish, and verify a unit test that a failed catalog workdir delete logs
      a warning and leaves the publish outcome unchanged

## 3. Integration check

- [ ] 3.1 Run
      `uv run pytest middleware/api/tests/unit/test_executor_shutdown.py middleware/api/tests/unit/test_git_repo.py middleware/api/tests/unit/test_consolidated_git_arc_store.py middleware/api/tests/unit/test_git_cache_cleanup.py --no-cov`
      and `uv run ruff check --config ruff.toml` on the touched files, and verify both succeed
