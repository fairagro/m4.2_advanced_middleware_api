# GitRepo ephemeral workdir — Tasks

## 1. Ephemeral workdirs in GitRepo

- [ ] 1.1 Change `GitRepo` create-or-update / get to allocate a unique directory under
      `cache_dir` (e.g. `mkdtemp` with prefix `git_repo_sync_`) instead of
      `cache_dir / arc_id`.
- [ ] 1.2 Keep `finally` cleanup so each invocation removes its own working directory
      (success and failure).
- [ ] 1.3 Ensure `_exists` remains ls-remote-only (no local workdir).

## 2. Orphan reclaim helper

- [ ] 2.1 Add a small age-gated reclaim helper for known ephemeral prefixes under
      `cache_dir` (`git_repo_sync_`, `catalog_finalize_`) plus stale legacy
      `cache_dir / <arc_id>`-style dirs.
- [ ] 2.2 Call the helper opportunistically from `GitRepo` (init and/or before sync)
      and optionally from consolidated finalize entry.
- [ ] 2.3 Use a TTL constant well above worst-case clone+push (hours).

## 3. Tests and docs

- [ ] 3.1 Unit/contract tests: two overlapping invocations for the same `arc_id` get
      distinct local paths; each cleans up its own dir.
- [ ] 3.2 Unit tests: reclaim deletes only stale matching dirs; preserves recent /
      unrelated paths.
- [ ] 3.3 Update `openspec/specs/arc-store/design.md` Decision 3 wording when
      archiving (unique per invocation, not only “temporary”).
- [ ] 3.4 Run focused `uv run pytest` for GitRepo / reclaim tests; close #347 when
      merged.
