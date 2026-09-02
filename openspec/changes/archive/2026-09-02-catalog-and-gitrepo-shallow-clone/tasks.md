# Catalog and GitRepo shallow clone — Tasks

## 1. Shallow clone in GitContext

- [x] 1.1 Pass `depth=1` to `Repo.clone_from` in `GitContext.__enter__` for fresh
      clones (no `.git` yet).
- [x] 1.2 Leave `_sync_existing_repo` and empty-remote init paths unchanged; do not
      add YAML/`GitCliSettings` clone-depth options.

## 2. Tests

- [x] 2.1 Unit test: `GitContext` clone invokes `clone_from` with `depth=1`.
- [x] 2.2 Confirm existing ConsolidatedGit publish and/or GitRepo bare-remote tests
      still pass (tip read/write/push).

## 3. Verify

- [x] 3.1 Run focused `uv run pytest` for GitContext / GitRepo / consolidated git
      tests.
- [ ] 3.2 Close [#346](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/346)
      when merged (note GitRepo included in scope).
