# Proposal

## Why

Harvester and sql-to-arc need a local stand-in for the Middleware API so they can run fullstack and automated tests
without CouchDB, RabbitMQ, or DataHUB. The thing under test is the **ARC on disk** — not production HTTP status
semantics. Consumers need a **light PyPI dependency** they can install in CI (not the full `api` package with
Celery/CouchDB/ Git). Today sql-to-arc keeps an in-tree demo server; this change ships a purpose-built stand-in as a
publishable workspace package.

## What Changes

- Add workspace package **`fairagro-middleware-api-local-offline`** (`middleware/api_local_offline/`) with enough `/v3`
  harvest and ARC HTTP for `ApiClient.harvest_arcs`, writing each accepted ARC under a configurable output root (arctrl)
  **before** HTTP success.
- Publish that package on the same PyPI/TestPyPI path as shared, api-client, and arc-validation (ci-cd: four packages).
- CLI entrypoint `middleware-api-local-offline` for compose/manual runs; in-process `create_local_offline_app` for ASGI
  test harnesses.
- Do **not** require production conflict/identity HTTP behaviour; do **not** depend on the heavy `api` package.
- **Out of scope:** adopting the package inside sql-to-arc / harvester (follow-ups
  [sql_to_arc#163](https://github.com/fairagro/m4.2_sql_to_arc/issues/163) and later harvester work); catalog finalize
  on disk; production Helm; `load-dev-secrets` (#439).

## Capabilities

### New Capabilities

- `local-offline-profile`: Local offline Middleware stand-in package — light HTTP for `ApiClient`, filesystem ARC
  output, PyPI distribution, no three production backends.

### Modified Capabilities

- `arc-store`: Document filesystem ARC persistence used by the local offline stand-in (write under output root; no Git
  remote).
- `ci-cd`: Publish a fourth Python package `fairagro-middleware-api-local-offline`.

## Impact

- New workspace member, publish matrix, MYPYPATH/pylint overlays, package README.
- Production Middleware API runtime unchanged (no `local_offline` module inside `api`).
- Issue [#440](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/440).
