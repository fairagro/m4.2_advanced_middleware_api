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
            ├─→ DocumentStore.increment_harvest_statistics
            └─→ DocumentStore.finalize_harvest
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
