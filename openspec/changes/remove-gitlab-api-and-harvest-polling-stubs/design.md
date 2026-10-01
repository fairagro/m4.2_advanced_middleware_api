# Design

## Context

Issue #182 hard-cuts the deprecated `GitlabApi` ArcStore after GitRepo became the only supported per-ARC backend.
Dual-slot configuration (`arc_store` + optional `consolidated_store`) already lives on `main`; this change only removes
the second per-ARC backend choice.

## Goals / Non-Goals

**Goals**

- Config accepts only `arc_store.git_repo` for per-ARC persistence (optional `consolidated_store` unchanged).
- Delete the `gitlab_api` package and all construction/resolution paths that select it.
- Align main `arc-store` spec/design, AGENTS.md, and operator docs with the hard cut.

**Non-Goals**

- Changing GitLab project metadata behavior for `GitRepo` (topics, title, description).
- Removing `python-gitlab` or helpers such as `sanitize_gitlab_api_project_name` used by the GitLab remote provider.
- Renaming system-external fixtures named `gitlab_api` that wrap a GitLab HTTP client for assertions.
- Soft-migration warnings that still parse `gitlab_api` and emit a custom message (hard fail via normal validation).
- Removing `HarvestConfig.grace_period_days` / `auto_mark_deleted` — reserved for #340 delete policy.

## Decisions

1. **Hard cut, not soft reject** — Nested `arc_store.gitlab_api` fails the same way as any other forbidden/extra field
   or missing `git_repo`. No dedicated migration error type.
2. **Keep harvest delete knobs** — Issue #182 also listed removing unused `grace_period_days` / `auto_mark_deleted`, but
   #340 plans to wire them for ARC lifecycle; retain the fields as pre-config stubs.
3. **Keep Helm `unset` of `gitlab_api` optional** — Chart may keep defensive stripping of obsolete keys from rendered
   config, or drop it once values no longer emit the key; either is fine if validation already forbids the nested slot.
4. **Main design.md rewrite at apply/archive** — Module overview stops describing `GitlabApi`; decision “Prefer GitRepo
   to GitlabApi” becomes “GitRepo only for per-ARC persistence”.

## Risks / Migrations

- **BREAKING for lingering deploys** still on `arc_store.gitlab_api` — they must switch to `git_repo` before upgrade.
- Unit tests that assert deprecation warnings or construct `GitlabApi` configs need deletion or rewrite to expect
  validation failure / `git_repo`-only success paths.
- Do not delete `test_persistence_gitlab_api.py` blindly if it primarily exercises GitLab _metadata_ via GitRepo; audit
  before remove.

## Open Questions

- None for MVP (lock-in: Refactoring + hard cut).
