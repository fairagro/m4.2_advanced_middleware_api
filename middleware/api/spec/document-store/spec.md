# Document Store (CouchDB)

The document store is the single persistence layer for all structured data in
the middleware. It uses **one CouchDB database** that holds three types of
documents:

1. **ARC documents** — the serialized RO-Crate content together with all
   lifecycle metadata for that ARC (content hash, timestamps, event log).
   Content and metadata are co-located in a single document, keyed by `arc_id`.
2. **Harvest documents** — metadata about a harvest run (owner, counters,
   status). Separate from ARC documents; referenced by `harvest_id`.
3. **Task records** — optional records written by background workers to track
   Celery task outcomes.

All three types share one database. Isolation between them is by document key
prefix, not by separate databases.

## Requirements

- [ ] On initialization, ensure the application database exists before use.
- [ ] On initialization, ensure CouchDB system databases (`_users`, `_replicator`)
      exist if they do not yet exist.
- [ ] Handle `412 Precondition Failed` (database already exists) as a success
      during initialization — parallel service startups must not cause crashes.
- [ ] Store ARC documents keyed by `arc_id`; return `is_new` and `has_changes`
      flags based on content hash comparison.
- [ ] Support harvest run lifecycle operations: create, retrieve, increment
      statistics counters, and finalize a harvest run.
- [ ] Append event records to an ARC document's event log.
- [ ] Release the underlying HTTP session and database client on shutdown.

## Edge Cases

Parallel service startup (two containers connecting simultaneously) → both attempt
database creation; `412 Precondition Failed` is treated as success, not an error.

ARC document already exists with identical content → `has_changes = False`; no
CouchDB write performed for the body; only timestamp fields may be updated.

`get_harvest` for unknown ID → returns `None`; callers raise `ResourceNotFoundError`.
