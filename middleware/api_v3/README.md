# fairagro-middleware-api-v3

Shared FastAPI route registration for the ApiClient harvest/ARC lifecycle (`/v3/harvests…`, `POST /v3/arcs`,
`GET /v3/liveness`). Backends implement `middleware.shared.v3_lifecycle.HarvestArcLifecyclePort`; production and
local-offline mount these routers with their own adapters.

This package depends on `fairagro-middleware-shared` and FastAPI. It must not import package `api`.
