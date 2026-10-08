# Design

## Context

See proposal.md — Why. Explore chose **D** over CouchDB-event-only option C: always enqueue; worker does change
detection + GitLab exists probe so DataHub wipes recover without hot-path GitLab calls.

## Goals / Non-Goals

**Goals:** Recover missing DataHub projects when CouchDB content is unchanged; keep ingest HTTP free of GitLab exists;
use Celery for the slower/optional work; prefer GitLab REST GET over git CLI for existence.

**Non-Goals:** Exists on ingest; relocating CouchDB `store_arc` into the worker; admin force-resync UI; changing hash
algorithm; switching change detection to trust `metadata.arc_hash` without re-hashing `existing.arc_content` (see D2a).

## Decisions

### D1: Always enqueue after successful persist

API path: after `store_arc` succeeds, always `dispatch_sync_arc`. Remove `should_trigger_git = is_new or has_changes`.

**Reason:** Worker is the right place for “do we still need Git?” including DataHub presence.

### D2: Content hash stays on the API persist path (required); worker only consumes the result

**Do not** move hashing fully into Celery. The API `store_arc` path MUST keep computing the incoming content hash and
deciding `has_changes` because that drives synchronous contracts:

- harvest-local `DuplicateArcError` → HTTP `409` when same harvest resubmits different content
- idempotent unchanged persist (`last_seen` / restore events without body rewrite)
- `metadata.arc_hash`, `last_changed`, `ARC_UPDATED` vs unchanged
- response `CREATED` / `UPDATED` semantics tied to `ArcStoreResult`

### D2a: Re-hash stored ARC bodies for change detection (keep; do not switch to `arc_hash` alone)

**Decision:** When an ARC document already exists, `has_changes` MUST continue to compare `hash(canonicalize(incoming))`
with `hash(canonicalize(existing.arc_content))` — i.e. **re-hash the stored body**. Do **not** decide change solely via
`metadata.arc_hash == incoming_hash` in this change (or as a silent follow-on).

```text
incoming_hash = hash(canonicalize(incoming))
has_changes = hash(canonicalize(existing.arc_content)) != incoming_hash
# then metadata.arc_hash = incoming_hash  (field updated for clients/ops; not the compare source)
```

**Reason:**

1. **Canonicalization evolves.** Volatile-field stripping and order/keyword rules have changed and may change again. Old
   documents may carry an `arc_hash` computed under a prior algorithm. Comparing only the stored field would treat
   logically identical re-submits as “changed” (or the reverse) after a hash-rule upgrade.
2. **Body is source of truth.** `arc_content` is what was persisted; re-hashing it under **current** rules is the
   correct semantic equality check (already documented in `couchdb.py`).
3. **Cost is acceptable.** Re-hash is CPU-only (~ms even for mid-size graphs) and dominated by CouchDB I/O and far
   cheaper than Git sync — not worth trading correctness for skipping one canonicalize+SHA of the stored body.
4. **Trusting `arc_hash` alone** would need an explicit migration (algorithm version on metadata, backfill, or
   fallback-to-rehash) — separate issue, not #338.

For Git decisions the worker MUST NOT re-derive CouchDB content comparison as the source of truth. Extend `ArcSyncTask`
with `is_new` / `has_changes` from `ArcStoreResult` after persist. Worker Git rule: flags + `project_exists` (D3). No
second full hash of the Celery RO-Crate payload for the skip gate.

**Reason (D2):** HTTP/idempotency need the hash on ingest; “change detection in the worker” means **Git skip vs sync**,
not relocating CouchDB content comparison. Always-enqueue (D1) still recovers DataHub wipes via exists probe.

### D3: Unchanged + exists ⇒ skip full sync; unchanged + missing ⇒ sync

```text
if is_new or has_changes:
    create_or_update(...)  # full path
else:
    if project_exists(arc_id):  # GitLab API GET; treat pending-deletion as missing
        # no Write, no git push; optional GIT_PUSH_SKIPPED / structured log reason=present_unchanged
    else:
        create_or_update(...)  # recreate / first push
```

**Reason:** Matches explore D; GET is cheap vs scaffold+git; intentional delete vs wipe both look “missing” — acceptable
per explore (recovery preferred).

### D4: `project_exists` on Git provider

Add `GitlabGitProvider.project_exists(arc_id) -> bool` (or ArcStore façade): `projects.get`, treat
`GitlabGetError`/pending-deletion/path rewrite as missing. **Must not** create projects. No git CLI.

**Reason:** `ensure_repo_exists` creates; skip path must not create empty projects without content sync.

### D5: Events / logging

- Full push success/failure/skipped unchanged from today’s `create_or_update` outcomes.
- When skipping because present+unchanged: log clearly; prefer existing `GIT_PUSH_SKIPPED` with message distinguishing
  “no commit” vs “datahub already has project, content unchanged”, or add a dedicated reason in the message string for
  ops grepping. New enum value only if existing events are insufficient (prefer message first to limit schema churn).

## Risks / Trade-offs

- [Celery/Rabbit load] → Accept for harvest size; monitor queue depth; exists GET should dominate cost for unchanged.
- [Race: delete between exists and skip] → rare; next harvest re-enqueues.
- [Token-less GitLab] → exists cannot run; fail closed to full sync or skip with warning — document in apply (prefer
  full sync attempt so behavior stays correct when git credentials exist for push).
- [ArcSyncTask payload growth] → two booleans only.

## Migration Plan

Deploy API+worker together. Old workers without exists logic still run full `create_or_update` (safe, heavier).
Rollback: restore enqueue gate.

## Open Questions

None blocking MVP after explore lock-in D. Force-resync admin remains a follow-up if product wants an explicit button
beyond automatic missing-project recovery.
