# Harvest-Context ARC Upload — Design

## Module Overview

`POST /v3/harvests/{harvest_id}/arcs` (`api/v3/harvests.py`) resolves the harvest
and `rdi`, then delegates to `ArcManager.create_or_update_arc`. HTTP status
codes for harvest-scoped identity conflicts come from that pipeline.

```text
Client (may retry on ConnectError)
    └─→ POST /v3/harvests/{harvest_id}/arcs
            ├─→ load harvest → rdi
            ├─→ authorize rdi
            └─→ ArcManager.create_or_update_arc(..., harvest_id=...)
                    ├─→ identical content already in this harvest → 200 UPDATED
                    └─→ same identifier, different content in this harvest → 409
```

## Key Decisions

1. **Identical harvest re-submit returns `200`, not `409`**
   — Clients that lose the HTTP response (e.g. `ConnectError` after the server
   already stored the ARC) must be able to retry the same POST without treating
   success as failure. Returning `200` with `UPDATED` makes the retry look like
   a normal success path, so the api-client can retry transport errors on this
   POST without special-casing `409`-as-success. A blanket `409` on every
   re-submit would force every lost-response retry into the error path (and, in
   the current api-client, into catastrophic harvest abort).

2. **Different content for the same identifier in one harvest returns `409`**
   — Within a single harvest run the ARC body for a given identifier is
   immutable. Rejecting a conflicting payload with a clear `409` prevents silent
   overwrites and keeps “one identifier → one object” guarantees. Callers that
   intentionally change content must start a new harvest (or use standalone
   `POST /v3/arcs`, which allows updates across calls).

3. **No second CouchDB document on either path**
   — ARC documents are keyed by `arc_id` derived from `(identifier, rdi)`.
   Idempotent success and conflict rejection both leave at most one document;
   neither path inserts a duplicate key.

## Compatibility

Changing identical harvest re-submit from `409` to `200` is a **behavioural
contract change** for `POST /v3/harvests/{harvest_id}/arcs` only.

| Caller assumption | Impact |
| ----------------- | ------ |
| First successful submit of a new ARC | Unchanged (`200`, `CREATED` / `UPDATED`). |
| Retry after lost response with the **same** body | **Breaking if the caller required `409`.** Becomes `200` / `UPDATED`. Preferred for transport retries. |
| Second submit with the **same** identifier but **different** body in one harvest | Still `409`; detail text may stay harvest-duplicate oriented. |
| Standalone `POST /v3/arcs` | Unchanged (already content-hash idempotent; different content remains an update). |
| Harvest statistics / finalize | Unchanged: counts are derived from ARC documents at finalize, not incremented per POST; identical retries do not create a second object to double-count. |
| api-client today | Does **not** retry POST on `ConnectError` (`POST` ∉ idempotent methods). Treating identical re-submit as `409` is also **catastrophic** and aborts the harvest — so a blind POST retry against the *current* server would be unsafe. After this server change, enabling POST retries is safe for identical bodies; conflicting `409` must stay non-success. |
| External clients that map any harvest `409` on ARC POST to “already submitted, continue” | Still correct for conflicting content; for identical retries they will simply take the success path instead — usually compatible. |
| External clients that **assert** `409` on intentional identical re-submit (tests / probes) | **Breaking** — must expect `200`. |

Wire format (`SubmitHarvestArcRequest`, `ArcResponse`) is unchanged; only the
status outcome for the identical-re-submit case changes.
