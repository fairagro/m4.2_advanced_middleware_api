# Harvest Management — Design

## Module Overview

`HarvestManager` (`business_logic/harvest_manager.py`) delegates all
persistence to `DocumentStore`. It adds ownership validation and configuration
defaults on top of the raw CRUD operations.

```text
API endpoint
    └─→ HarvestManager
            ├─→ DocumentStore.create_harvest
            ├─→ DocumentStore.get_harvest
            ├─→ DocumentStore.get_harvest_statistics  (at terminal transition)
            └─→ DocumentStore.update_harvest          (transition_harvest)
```

## Key Decisions

1. **Ownership validated in `HarvestManager`, not in the API layer**
   — The `client_id` check belongs in the service layer so that it is enforced
   regardless of which API version or endpoint triggers the operation. Placing
   it in the router would duplicate the check across v1/v2/v3 handlers.

2. **`ResourceNotFoundError` before ownership check**
   — A missing harvest raises `ResourceNotFoundError` unconditionally. Checking
   ownership on a non-existent resource would require reading a null document;
   returning a 404 first is the safer and simpler behaviour.

3. **`HarvestConfig` holds all defaults**
   — Timeout durations, retry counts, and other harvest-level defaults live in
   `HarvestConfig` (a Pydantic model). Application code reads them from the
   config object rather than hardcoding values, making them overridable via
   environment variables or YAML without a code change.

4. **`transition_harvest` accepts a pre-fetched `HarvestDocument`, not a `harvest_id`**
   — The router always fetches the harvest before calling into the service layer
   (for RDI auth and existence checks). Passing the already-fetched document
   avoids a redundant round-trip to CouchDB and removes the dead
   `pre_fetched or await get_harvest()` fallback path. Responsibility for
   handling a missing harvest therefore stays in the router (HTTP 404), while
   `transition_harvest` focuses solely on ownership validation, the RUNNING
   guard, and the DB write.

5. **Single `transition_harvest` replaces separate `complete_harvest` / `cancel_harvest` / `fail_harvest` methods**
   — All three terminal transitions share the same shape: ownership check →
   RUNNING guard → `DocumentStore.update_harvest`. A single generic method
   parameterised over `target_status` avoids duplicating that logic three
   times. The only special case is `COMPLETED`: it also persists the current
   statistics snapshot (same behaviour as the old `complete_harvest`).

6. **`PATCH /v3/harvests/{harvest_id}` as the canonical state-transition endpoint**
   — A single PATCH endpoint with `{"status": "..."}` in the body covers all
   terminal transitions. The legacy `DELETE /{harvest_id}` (cancel) and
   `POST /{harvest_id}/complete` endpoints are kept for backward compatibility
   but are not the preferred path for new clients. The API client's
   `cancel_harvest()` and `fail_harvest()` methods both call PATCH internally.
