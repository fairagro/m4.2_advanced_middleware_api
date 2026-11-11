# Proposal

## Why

Production `/v3` harvest/ARC routers and the local-offline stand-in each register overlapping HTTP surfaces. Paths and
`response_model` shapes can drift while backends stay intentionally different (offline soft-matches `ApiClient`;
production keeps 409/identity semantics). Issue #440 shipped the stand-in MVP with duplicated handlers; #613 extracts a
shared route + port layer so the ApiClient harvest lifecycle cannot silently diverge.

## What Changes

- Add a new workspace package (FastAPI + `shared`) that owns **route registration** for the ApiClient harvest lifecycle
  (`POST/GET/PATCH /v3/harvests…`, harvest ARC submit, complete, standalone `POST /v3/arcs`, minimal liveness) using
  `shared.api_models.v3` response models.
- Define a **Protocol / port** for the operations those routers call; production and offline supply separate adapters
  (production: HarvestManager/ArcManager + auth deps; offline: filesystem ARC write + in-memory harvest state, soft
  semantics retained).
- Move `calculate_arc_id` into `middleware.shared` and delete the duplicated offline copy / `api.utils` definition so
  identity hashing cannot drift.
- Wire production `api` and `api_local_offline` to mount the shared routers; offline MUST remain installable without
  package `api`.
- Add a focused contract/smoke test that both apps expose the same paths / `response_model` surface for that lifecycle.
- **Out of scope for this change:** list-harvests, deprecated complete/cancel aliases, full system router
  (`whoami`/`version`/`health` auth), rate-limit/admission middleware, forcing offline 409 parity.

## Capabilities

### New Capabilities

- `v3-http-contract`: Shared FastAPI harvest/ARC route surface and operation port for production and local-offline
  mounts (lifecycle MVP only).

### Modified Capabilities

- `local-offline-profile`: Stand-in MUST mount the shared `v3-http-contract` routers via an offline adapter; soft
  semantics remain adapter-local; still no dependency on package `api`.

## Impact

- New package under `middleware/` (workspace member) depending on `fairagro-middleware-shared` + FastAPI.
- `middleware/shared`: Protocol + `calculate_arc_id`; no FastAPI dependency.
- `middleware/api`: mount shared routers; remove/redirect duplicated v3 harvest/ARC route modules for the MVP surface;
  import `calculate_arc_id` from shared.
- `middleware/api_local_offline`: depend on the new package; replace hand-rolled `add_api_route` handlers with shared
  routers + offline adapter; drop local `arc_id.py`.
- Import-linter / principles: document the new package’s allowed edges (`api` and `api_local_offline` → new package →
  `shared`; new package ↛ `api`).
- Wire HTTP contracts in `arc-upload` / `harvest-arc-upload` / `harvest-manager` stay as-is for production status codes;
  this change is structural wiring, not a production semantics change.
