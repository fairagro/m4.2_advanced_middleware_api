# Proposal

## Why

When CouchDB already holds identical ARC content, ingest skips Celery (`should_trigger_git = is_new or has_changes`).
After a DataHub wipe (or a never-successful push), harvests return `200` while GitLab stays empty and Celery stays idle.
Operators need recovery without a full write+git sync on every unchanged ARC on the API hot path.

Explore lock-in for #338: **pivot D** — always enqueue after successful persist; decide skip vs sync in the Celery
worker; on unchanged content, use a **fast GitLab API project-exists** probe (not git CLI) before optional full sync.

## What Changes

- After a successful CouchDB store, the API **always** enqueues `sync_arc_to_gitlab` (remove the unchanged skip gate).
- Content hash / `has_changes` **remain on the API** `store_arc` path (HTTP idempotency, harvest `409`, metadata
  events). The worker receives `is_new` / `has_changes` on `ArcSyncTask` and does **not** own CouchDB content
  comparison.
- Worker when content is unchanged: call GitLab API “does project `arc_id` exist (and not pending deletion)?”; if yes →
  no scaffold write / git push; if no → full `create_or_update` sync.
- Worker when content is new/changed: full sync as today.
- Implement `ArcStore.exists` for the GitLab-backed store via a read-only provider probe (`repo_exists` / project GET),
  no create, no git CLI — worker skip gate reuses `exists`, not a new ArcStore method.
- Logging/metrics: reason codes (`changed` / `missing_on_datahub` / `present_unchanged`).
- OpenSpec deltas for `arc-manager` (and `arc-store` if the exists probe is part of the store/provider contract).
- Unit tests for enqueue-always + worker branch matrix; update system tests that assumed “unchanged ⇒ no enqueue”.

Non-goals: exists check on the ingest HTTP path; moving CouchDB persist into Celery; force-resync admin UI (exists-miss
covers wipe); changing content-hash canonicalization; removing `GIT_PUSH_SUCCESS` event semantics for other consumers.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-manager`: Always schedule per-ARC Git sync after successful persist; worker owns skip vs sync using change
  detection + DataHub project existence.
- `arc-store`: Git remote provider MUST expose a lightweight project-existence check used by the worker skip path.

## Impact

- `arc_manager.create_or_update_arc` enqueue logic; `sync_to_gitlab` / `GitRepo` / `GitlabGitProvider`.
- Celery volume rises (one task per successful ingest ARC); each unchanged hit should be a cheap API GET, not disk+git.
- Channel: `build/issue-338-always-enqueue-git-exists-check`. Related: #337 (ops wipe gap).
