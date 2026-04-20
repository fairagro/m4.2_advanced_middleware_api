# Document Store — Design

## Module Overview

`CouchDBClient` (`document_store/couchdb_client.py`) wraps `aiocouch` and
exposes typed async methods. `DocumentStore` (`document_store/__init__.py`)
is a thin facade that routes calls to `CouchDBClient`.

```text
DocumentStore
    └─→ CouchDBClient (aiocouch)
            └─→ CouchDB server
```

## Key Decisions

1. **System database initialization inside `connect()`**
   — CouchDB requires `_users` and `_replicator` system databases to exist
   before application databases can be reliably created. Initializing them in
   `connect()` removes the need for a separate `couchdb-init` sidecar or
   init container, simplifying the deployment topology.

2. **Race-condition-safe creation via `412` tolerance**
   — Multiple service replicas may call `connect()` simultaneously. Using
   `PUT /db` and treating `412 Precondition Failed` as success is the
   standard CouchDB pattern for idempotent database creation; it is simpler
   and more reliable than a `HEAD`-then-`PUT` check-and-create pattern.

3. **Content hash for idempotency**
   — Comparing a SHA-256 hash of the serialized ARC JSON avoids unnecessary
   CouchDB writes and downstream Celery tasks when a client re-submits an
   unchanged ARC. The hash is stored as a field on the document.

4. **Concrete types for `_client` and `_db`**
   — Annotating `_client: CouchDB | None` and `_db: Database | None` (instead
   of `Any`) allows Mypy to catch incorrect attribute access at compile time.

5. **Lazy `aiohttp.ClientSession` for raw calls**
   — Some operations (e.g., index management) require direct HTTP calls not
   covered by the `aiocouch` API. A shared session is created lazily on first
   use and closed alongside the main client to avoid resource leaks.
