# Tasks

## 1. Config & ArcStore wiring

- [x] 1.1 Remove `gitlab_api` nested field / validators from ArcStore config models; require `git_repo` only
- [x] 1.2 Strip `GitlabApi` from factory, resolution, and package exports; delete `arc_store/gitlab_api/`
- [x] 1.3 ~~Remove `HarvestConfig.grace_period_days` and `auto_mark_deleted`~~ — **kept** for #340 delete policy

## 2. Tests

- [x] 2.1 Delete or rewrite unit tests that construct `GitlabApi` / expect deprecation warnings
- [x] 2.2 Add/adjust config tests: nested `gitlab_api` rejected; `git_repo` (+ optional consolidated) accepted
- [x] 2.3 Harvest document fixture still uses legacy nested `grace_period_days` / `auto_mark_deleted` keys (ignored by
      schema)
- [x] 2.4 Keep system-external GitLab _client_ fixtures; ensure they still configure `arc_store.git_repo`

## 3. Helm, examples, docs

- [x] 3.1 Remove `gitlab_api` from Helm values / examples; simplify NOTES / config-secret as needed
- [x] 3.2 Update `AGENTS.md` Spec-to-Code Mapping and any architecture / gitlab docs that list `GitlabApi`

## 4. Specs & quality

- [x] 4.1 Apply delta into `openspec/specs/arc-store/spec.md` and refresh `design.md` (GitRepo-only overview)
- [x] 4.2 Run unit tests for touched modules plus Ruff / mypy / pylint on `middleware/`
