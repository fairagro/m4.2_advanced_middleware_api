# GitRepo ephemeral workdir — Design

## Context

See `proposal.md` and [#347](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/347).
Today `GitRepo._get_context_config` sets `local_path = cache_dir / arc_id`. Both
`_create_or_update` and `_get` clone into that path, mutate the tree, then
`shutil.rmtree(local_path)` in `finally`. Overlapping Celery prefork workers or
thread-pool tasks for the same `arc_id` share the path.

Consolidated catalog finalize already uses
`tempfile.mkdtemp(prefix="catalog_finalize_", dir=cache_dir)` and deletes it in
`finally`. `openspec/specs/arc-store/design.md` Decision 3 already says “fresh
temporary clones”; this change makes `GitRepo` match that intent.

`gitlab_api` stays out of scope (legacy).

## Goals / Non-Goals

**Goals:**

- Unique local workdir per `GitRepo` create-or-update / get invocation.
- Always delete that workdir in `finally`.
- Best-effort, age-gated orphan reclaim under `cache_dir` for ephemeral prefixes
  (and legacy `cache_dir / <arc_id>` leftovers).
- Keep remote path/slug = `arc_id` unchanged.

**Non-Goals:**

- File or distributed locks.
- Skip/dedupe concurrent pushes for the same ARC.
- Changing Celery `--concurrency` as the fix.
- Touching `gitlab_api`.
- Background cleanup daemons or Kubernetes CronJobs.

## Decisions

### 1. Unique `mkdtemp` under `cache_dir` for GitRepo

**Choice:** Replace `cache_dir / arc_id` with
`tempfile.mkdtemp(prefix="git_repo_sync_", dir=cache_dir)` (or equivalent unique
path) at the start of each `_create_or_update` / `_get` that needs a clone. Pass
that path into `GitContextConfig.local_path`. Keep existing `finally: rmtree`.

**Why:** Matches consolidated finalize; eliminates shared-path races without
locks; aligns with documented “fresh temporary clones”.

**Alternatives:**

- Lock keyed by `arc_id` — rejected (process-local locks miss multi-replica;
  distributed locks are overkill for theoretical race).
- Lower Celery concurrency only — rejected (thread pool and multi-replica still
  overlap).

### 2. Shared age-gated orphan sweep

**Choice:** Small helper (e.g. under arc_store / git CLI helpers) that, given
`cache_dir`, prefixes (`git_repo_sync_`, `catalog_finalize_`), optional legacy
non-prefix dirs, and TTL (default on the order of hours, longer than a worst-case
clone+push), deletes matching directories whose mtime/ctime is older than TTL.
Call opportunistically from `GitRepo` init and/or before a sync; optionally from
consolidated finalize entry as well.

**Why:** Crashes leave orphans once paths are ephemeral; opportunistic sweep
avoids a scheduler. Shared helper keeps both backends consistent.

**Alternatives:**

- No orphan cleanup — rejected (user wants reclaim; cheap to add).
- Cron sidecar — rejected for this change.

### 3. No change to remote identity or push semantics

**Choice:** Remote repo path remains `arc_id`. Concurrent successful syncs still
follow last-successful-push on the remote.

**Why:** Issue is local FS races only; remote semantics already accepted.

## Risks / Trade-offs

- **[Risk] Orphan sweep deletes an in-flight long sync** → Mitigation: TTL well
  above expected max git operation (hours, not minutes); only matching prefixes /
  legacy shapes.
- **[Risk] More mkdtemp churn / disk** → Mitigation: same as consolidated;
  directories already short-lived; sweep reclaims crashes.
- **[Risk] Legacy `cache_dir / arc_id` dirs after deploy** → Mitigation: include
  them in reclaim when they match the old deterministic layout and are stale.

## Migration Plan

- Deploy workers with unique workdirs + sweep; no remote migration.
- First post-deploy syncs leave no shared `cache_dir / arc_id` usage; stale legacy
  dirs age out via sweep.

## Open Questions

None for implementation. TTL default can be a named constant (or config later)
without changing the requirement text.
