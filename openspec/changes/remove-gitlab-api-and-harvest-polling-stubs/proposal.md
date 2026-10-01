# Proposal

## Why

Deprecated `arc_store.gitlab_api` / `GitlabApi` remains after the GitRepo migration. Dual-slot work deferred this
cleanup to #182; keeping both backends increases validation surface and confuses deployers.

## What Changes

- **BREAKING:** Remove the deprecated `GitlabApi` ArcStore backend and nested `arc_store.gitlab_api` configuration.
  `arc_store` MUST configure exactly `git_repo` (plus optional `consolidated_store`).
- Delete `middleware/api/.../arc_store/gitlab_api/` and its dedicated unit tests; strip factory/resolution/config wiring
  and Helm/example references to that backend.
- Update `openspec/specs/arc-store/` requirements that still allow `gitlab_api`, plus AGENTS.md / architecture docs that
  still describe the deprecated backend.
- Keep GitLab _project metadata_ helpers used by `GitRepo` (`sanitize_gitlab_api_project_name`, `python-gitlab`
  provider) and system-external fixtures that talk to a GitLab server via the python-gitlab client (not the ArcStore).
- **Keep** `HarvestConfig.grace_period_days` / `auto_mark_deleted` — reserved for ARC lifecycle delete policy (#340);
  not removed in this change despite the original issue wording.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Dual-slot selection and finalize no-op language MUST drop deprecated `gitlab_api` / `GitlabApi`; per-ARC
  `arc_store` accepts only nested `git_repo`.

## Impact

- **Code:** `arc_store_config.py`, `factory.py`, `resolution.py`, `gitlab_api/` package removal; unit tests that
  construct or warn about `GitlabApi`; Helm `values.yaml` / `config-secret.yaml` / `NOTES.txt`.
- **Deploy:** Any remaining `arc_store.gitlab_api` configs fail validation (intentional hard cut).
- **Specs/docs:** `openspec/specs/arc-store/{spec,design}.md`, `AGENTS.md`, gitlab/architecture docs mentioning the
  deprecated backend.
- **Out of scope:** Renaming unrelated `gitlab_api` test fixture names; removing GitLab REST helpers used only to assert
  pushed projects under `GitRepo`; removing harvest delete-policy config knobs (#340).
