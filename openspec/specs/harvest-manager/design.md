# Harvest Management — Design

## Module Overview

`HarvestManager` (`business_logic/harvest_manager.py`) delegates persistence to `DocumentStore` and adds ownership
validation and configuration defaults.

```text
API endpoint
└─→ HarvestManager
    ├─→ DocumentStore.create_harvest
    ├─→ DocumentStore.get_harvest
    ├─→ DocumentStore.get_harvest_statistics  (terminal transition)
    └─→ DocumentStore.update_harvest           (transition_harvest)
```

## Key Decisions

1. **Validate ownership in `HarvestManager`** — This makes the `client_id` check consistent across API versions and
   endpoints.
2. **Return `ResourceNotFoundError` before checking ownership** — A missing document always produces not-found behavior;
   ownership cannot be checked without one.
3. **Put defaults in `HarvestConfig`** — Timeouts, retries, and harvest defaults are Pydantic configuration rather than
   application hardcodes.
4. **Pass pre-fetched documents to `transition_harvest`** — Routers already fetch a harvest for existence and RDI
   checks. Passing it avoids a second CouchDB read; the router owns the HTTP `404`, while the service owns ownership,
   RUNNING guard, and write.
5. **Use one terminal-transition method** — `transition_harvest` takes a target status to avoid separate duplicated
   complete/cancel/fail methods. `COMPLETED` additionally persists the current statistics snapshot.
6. **Make `PATCH /v3/harvests/{harvest_id}` canonical** — `{"status": "..."}` covers terminal transitions. Legacy
   delete-cancel and complete endpoints remain compatible, while API-client cancellation and failure use PATCH.
