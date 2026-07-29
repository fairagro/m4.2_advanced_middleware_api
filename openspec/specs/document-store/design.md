# Document Store — Design

## Module Overview

`CouchDBClient` (`document_store/couchdb_client.py`) wraps `aiocouch` with typed asynchronous methods. `DocumentStore`
(`document_store/__init__.py`) is a thin facade over it.

```text
DocumentStore
└─→ CouchDBClient (aiocouch)
    └─→ CouchDB server
```

## Key Decisions

1. **Initialize system databases in `connect()`** — CouchDB requires `_users` and `_replicator` before application
   databases can be reliably created. Doing this in the client eliminates the `couchdb-init` sidecar and init
   container.
2. **Tolerate `412` during create** — Parallel replicas use `PUT /db`; treating `412 Precondition Failed` as success
   makes creation idempotent and avoids a race-prone `HEAD` then `PUT`.
3. **Hash content for idempotency and harvest-local identity** — SHA-256 of serialized ARC JSON prevents redundant
   writes and downstream work. `calculate_arc_id(identifier, rdi)` trims both inputs; within a repeated
   `last_harvest_id`, matching hashes succeed unchanged and differing hashes raise `DuplicateArcError`.
4. **Use concrete `_client` and `_db` types** — `CouchDB | None` and `Database | None` replace `Any`, allowing Mypy to
   catch misuse.
5. **Create raw HTTP sessions lazily** — A shared `aiohttp.ClientSession` supports operations outside aiocouch and
   closes with the main client to avoid leaks.
