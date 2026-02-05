# Consolidating CouchDB Client and Tracing Refinement

This plan addresses the redundancy in the `CouchDBClient` implementation and identifies the next steps for modernizing the observability stack using Pydantic Logfire.

## User Review Required

> [!IMPORTANT]
> I am proposing to replace the current OpenTelemetry (OTLP) tracing/logging boilerplate in `middleware/shared/src/middleware/shared/tracing.py` with **Pydantic Logfire**. 
> Logfire is built on OpenTelemetry but offers much deeper integration with Pydantic models, which are used extensively throughout this project. 
> 
> **Benefits:**
> - Drastically reduces boilerplate (from ~150 lines to ~15 lines).
> - Automatically captures and visualizes Pydantic validation errors.
> - Unified interface for logs, spans, and metrics.
> - OTLP-compatible (can still export to Signoz/Jaeger if desired).

## Proposed Changes

### [Component] Shared Configuration & Client

Move CouchDB related configuration and the "fixed" client implementation to the `shared` package to ensure consistency across the API and Workers.

#### [MODIFY] [config_base.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/shared/src/middleware/shared/config/config_base.py)
- Move `CouchDBConfig` from the API package to `shared`.

#### [MODIFY] [couchdb_client.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/shared/src/middleware/shared/couchdb_client.py)
- Overwrite with the improved version from the API package (handling the missing `aiocouch` members correctly).

#### [DELETE] [couchdb_client.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/couchdb_client.py)
- Remove the redundant implementation.

#### [MODIFY] [config.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/config.py)
- Update to import `CouchDBConfig` from `shared.config.config_base`.

---

### [Component] API Health Monitoring

Update the health check routes to properly monitor CouchDB using the unified client and the recently added model fields.

#### [MODIFY] [api.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/api.py)
- Update `_setup_health_route` (v1) and `_setup_health_route_v2` to:
    - Include `couchdb_reachable` logic.
    - Properly initialize the shared `CouchDBClient` for the health check.

---

### [Component] Observability (Optional/Future)

#### [MODIFY] [tracing.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/shared/src/middleware/shared/tracing.py)
- (Proposed) Replace OTLP boilerplate with `logfire.configure()`.

## Verification Plan

### Automated Tests
- Run `uv run pytest middleware/api/tests/unit` to ensure existing logic still works with the consolidated client.
- Test the health check endpoint `/v1/health` and `/v2/health` to confirm `couchdb_reachable` reports correctly.

### Manual Verification
- Verify that Logfire (if enabled) captures the `ArcDocument` and `HarvestDocument` validations in the Logfire dashboard.
