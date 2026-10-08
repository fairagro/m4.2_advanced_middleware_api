# Tasks

## 1. Task payload and API enqueue

- [ ] 1.1 Extend `ArcSyncTask` with `is_new` / `has_changes` (or equivalent) from `ArcStoreResult` and verify model
      round-trip / Celery JSON dump still validates
- [ ] 1.2 Change `ArcManager.create_or_update_arc` to always enqueue after successful store; pass change flags on the
      task; verify unit tests that previously expected skip-on-unchanged now expect enqueue

## 2. GitLab exists probe

- [ ] 2.1 Add read-only `project_exists(arc_id) -> bool` on `GitlabGitProvider` (GET; pending-deletion ⇒ false; no
      create); verify unit tests with mocked Gitlab client for present / missing / pending deletion
- [ ] 2.2 Expose the probe to the worker sync path (store/provider façade as needed) without calling it from the HTTP
      ingest path; verify no ingest-path call sites

## 3. Worker skip vs full sync

- [ ] 3.1 In `sync_to_gitlab` / worker entry: if new or changed → full `create_or_update`; if unchanged and
      `project_exists` → skip write/push with clear log/event message; if unchanged and missing → full sync; verify unit
      tests cover the three branches
- [ ] 3.2 Update system/integration expectations that assumed “unchanged ⇒ no Celery enqueue”; verify targeted tests
      pass

## 4. Specs / docs check

- [ ] 4.1 Align log reason strings with design (changed / missing_on_datahub / present_unchanged) and note in AGENTS or
      short ops blurb if needed; verify strings appear in tests or documented examples
