# Tasks

## 1. Detect missing app DB and single-flight ensure

- [x] 1.1 Add a guarded `ensure_initialized` (or equivalent) on the document store / CouchDB client that clears a stale
      client when the application DB is gone, re-runs system DB + app DB creation (`412` tolerant), and re-runs index
      `setup`; verify with unit tests that a second concurrent caller awaits the same in-flight ensure
- [x] 1.2 Classify database-missing vs document-missing `NotFoundError` (or equivalent) so document 404 does not trigger
      re-init; verify unit tests for both cases

## 2. Write-path recovery and HTTP mapping

- [x] 2.1 On classified app-DB-missing failures during store writes/reads that need the DB, call ensure once and retry
      the operation once; verify unit tests that wipe → ensure → successful retry
- [x] 2.2 Map “re-init in progress / failed / still missing” to a typed error that HTTP handlers turn into **503** (not
      unhandled 500); verify API unit or handler tests for harvest create (or equivalent) return 503 while recovery
      fails or is incomplete

## 3. Readiness / health

- [x] 3.1 Change CouchDB readiness (and document-store health used for it) so success requires the configured
      application DB to exist; verify unit tests: empty server / missing DB → not ready; after ensure → ready
- [x] 3.2 Optionally invoke the same ensure from the readiness path when the app DB is missing; verify readiness
      recovers after a simulated wipe without requiring a write

## 4. Celery / integration check

- [x] 4.1 Confirm Celery long-lived `BusinessLogic` / store uses the same ensure path (shared client code or explicit
      call sites); verify with a focused unit or worker test that a missing app DB triggers ensure rather than raw
      `NotFoundError` escape
- [x] 4.2 Add or extend a system/integration test (or documented manual ops check if env-heavy) covering: wipe CouchDB
      while process stays up → next harvest create or readiness causes re-init → harvest create succeeds; verify the
      chosen test or scripted check passes locally
