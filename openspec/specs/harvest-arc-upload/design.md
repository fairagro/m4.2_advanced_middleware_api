# Harvest-Context ARC Upload — Design

## Module Overview

`POST /v3/harvests/{harvest_id}/arcs` (`api/v3/harvests.py`) resolves the harvest and RDI, authorizes it, and delegates
to `ArcManager.create_or_update_arc`. Harvest identity outcomes are defined in `openspec/specs/arc-manager/`.

```text
Client (may retry on ConnectError)
└─→ POST /v3/harvests/{harvest_id}/arcs
        ├─→ load harvest → rdi
        ├─→ authorize rdi
        └─→ ArcManager.create_or_update_arc(..., harvest_id=...)
                ├─→ identical content in this harvest → 200 UPDATED
                └─→ same identifier, different content → 409
```

## Key Decisions

1. **Identical re-submit returns `200`, not `409`** — A client that loses the original response can retry normally. `200
   UPDATED` lets API clients safely retry a transport failure without treating a successful submission as
   catastrophic harvest failure.

2. **Conflicting content remains `409`** — ARC content for one identifier is immutable within a harvest. Clients that
   intentionally change it must start a new harvest or use standalone `POST /v3/arcs`.

3. **Neither path creates a second CouchDB document** — `arc_id` derives from `(identifier, rdi)`; idempotent success
   and conflict both preserve the one-object guarantee.

## Compatibility

The identical re-submit behavior is a contract change for this endpoint only. First submissions remain `200`; same-body
lost-response retries become `200 UPDATED`; different bodies remain `409`; standalone upload is unchanged. Harvest
statistics remain finalization-derived, so identical retries cannot double count. Existing callers that assert `409` for
intentional identical re-submission must update their expectation; the request and response wire formats remain
unchanged.
