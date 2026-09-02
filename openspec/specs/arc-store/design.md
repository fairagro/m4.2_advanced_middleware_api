# ARC Store — Design

## Module Overview

`ArcStore` (`arc_store/__init__.py`) defines Git persistence. `GitRepo` (`arc_store/git_repo/`) is the primary,
Git-server-agnostic implementation: it clones through SSH or HTTPS, writes arctrl ISA files, and pushes. `GitlabApi`
(`arc_store/gitlab_api/`) is deprecated and retained only for compatibility.

`ArcManager.sync_to_gitlab` parses queued JSON, selects the backend, and records CouchDB events. The store only handles
Git.

```text
ArcManager.sync_to_gitlab(rdi, arc)
├─→ parse_rocrate(arc)
├─→ ARC.from_rocrate_json_string(...)
└─→ ArcStore.create_or_update(arc_id, arc_obj, rdi=...)
    └─→ GitRepo (or deprecated GitlabApi)
        ├─→ RemoteGitProvider.ensure_repo_exists(arc_id, metadata)
        ├─→ clone / pull
        ├─→ write ISA files via arctrl WriteAsync
        └─→ commit + push
```

## GitRepo Implementation

`GitRepo` clones or pulls to a temporary directory, calls `arctrl.ARC.WriteAsync`, stages all changes, commits and
pushes, then cleans up. `RemoteGitProvider` injects SSH or HTTPS credentials. At push time, `is_transient_git_error`
produces `ArcStoreTransientError`; soft repository or branch errors are permanent, as are other `GitCommandError`s.

## GitLab Project Metadata

`GitRepo` derives `GitProjectMetadata` with `git_project_metadata_from_arc(arc, rdi, arc_id=...)` before
`GitlabGitProvider.ensure_repo_exists`. GitLab `path` is `arc_id`, `name` is `{sanitized arc.Identifier} - {rdi}`,
description combines RO-Crate name then description and is capped at 2000 characters, and topics are exactly the
resolved RDI topic.

`GitRepoConfig.rdi_gitlab_topics` maps middleware RDI names to GitLab labels, for example `edal` to `e!DAL`. With empty
`known_rdis` (tests), unmapped RDIs use `normalize_gitlab_topic`; otherwise `Config` and `WorkerConfig` require one
non-empty mapping per known RDI. Existing projects are saved only when `apply_gitlab_project_metadata` detects changed
values. Non-GitLab providers accept metadata for a uniform interface and ignore it for bare repositories.

## Key Decisions

1. **Separate transient from permanent failures** — `ArcStoreTransientError` lets `ArcManager` decide to retry network
   and availability failures; other exceptions are permanent.
2. **Prefer `GitRepo` to `GitlabApi`** — Clone-and-push avoids REST commit action limits, is simpler, and works across
   Git servers. The REST implementation remains temporarily compatible.
3. **Use unique ephemeral local clones** — Each create-or-update or get that
   needs a working tree allocates a dedicated temporary directory under
   `cache_dir` (not a stable `cache_dir / arc_id` path). This avoids filesystem
   races across Celery worker processes and thread-pool workers. Directories are
   removed after each operation; stale orphans are reclaimed best-effort.
4. **Isolate credential injection** — `RemoteGitProvider` hides SSH and HTTPS authentication details from `GitRepo`.
5. **Use hashed paths and readable titles** — `arc_id` keeps clone URLs stable, while title and topic make GitLab
   browsing practical without duplicating RDI in descriptions.
6. **Refresh metadata on every sync** — Re-sync updates older projects created before metadata support without a
   separate migration.
