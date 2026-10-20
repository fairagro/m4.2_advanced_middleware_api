# Design

## Context

Startup already runs `DocumentStore.connect()` + `setup()` (system DBs, app DB, indices) via `BusinessLogic.startup`.
`CouchDBClient.connect()` returns immediately when `_client is not None`, so a wiped CouchDB leaves a stale handle.
`health_check` / readiness only prove the server answers, not that the configured application DB exists. Explore lock-in
for #341: **option C** — lazy re-init on missing app DB (single-flight) plus readiness that verifies the app DB.

## Goals / Non-Goals

**Goals:**

- Re-run the same init work as startup when the app DB (or required system DBs) disappears while the process lives.
- Single-flight re-init; one retry of the failing operation after success.
- 503 (or equivalent service-unavailable) during re-init / when recovery fails; no generic 500 for recoverable wipe.
- Readiness fails when the app DB is missing; may trigger the same ensure path.
- Same behaviour for API and Celery long-lived store instances.

**Non-Goals:**

- DataHub / GitLab wipe recovery (#337 / #338).
- Changing CouchDB auth, URL config, or multi-tenancy.
- Migrating or restoring wiped document contents (re-init creates empty DB + indices only).
- Distributed locking across pods beyond CouchDB’s own `412` create races (per-process mutex is enough).

## Decisions

### D1: Single-flight `ensure_initialized` (reconnect + setup)

Expose one idempotent ensure path that:

1. Detects “app DB missing” (HEAD/GET of configured DB name, or classified `NotFoundError` from aiocouch that means the
   **database** is gone — not a missing document).
2. Clears stale `_client` / `_db` when the server is up but the DB is gone (so `connect()` does not early-return
   forever).
3. Runs `ensure_system_databases` + create/open app DB + `setup()` indices (same as startup).
4. Uses an `asyncio.Lock` (or equivalent) so concurrent callers await one in-flight ensure.

**Alternative rejected:** Only restart pods — fails operator expectation and ACs.

### D2: Classify database-missing vs document-missing

aiocouch `NotFoundError` is used for both. Classification MUST use context (operation was against DB handle that
disappeared, explicit DB existence check, or HTTP status/reason for “database does not exist”). Document 404 MUST NOT
trigger re-init.

### D3: Write path — ensure + retry once

On classified DB-missing failure: `await ensure_initialized()` then retry the store operation once. If ensure fails or
the second attempt still sees DB missing → raise a typed error mapped to HTTP **503** (and optionally `Retry-After`).

### D4: Readiness uses app DB existence

Change CouchDB readiness/health used for probes so “CouchDB OK” means server reachable **and** configured app DB exists.
If missing, fail readiness; readiness MAY call `ensure_initialized()` so the next probe passes after recovery without
waiting for a write.

**Note:** Current `ApiHealthService._check_couchdb` only GETs the server root — that stays green on empty `_all_dbs`.
Wire readiness through the document store (or a DB existence check) instead of (or in addition to) root URL.

### D5: Celery

Workers that call `BusinessLogic.startup` once and reuse the store MUST use the same ensure path on store operations so
wipe recovery does not require restarting Celery deployments either.

## Risks / Trade-offs

| Risk                                              | Mitigation                                                                                                             |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Misclassified doc 404 → recreate storm            | Strict DB-missing classification + unit tests                                                                          |
| Re-init under load / many pods                    | Per-process lock + CouchDB `412` tolerance (already in startup)                                                        |
| Empty DB after wipe looks “healthy” but data gone | Expected; operators must re-harvest — out of scope                                                                     |
| Indices create latency on first post-wipe request | Acceptable; readiness can warm ensure before traffic                                                                   |
| Permanent auth/network failure loops              | Ensure failures → 503; do not spin forever without backoff in the request path (one ensure attempt per request window) |

## Migration / rollout

No schema migration. Deploy API (+ Celery) with the change; verify by wiping CouchDB PVC/data while pods stay up and
confirm harvest create recovers and readiness flakes then recovers.
