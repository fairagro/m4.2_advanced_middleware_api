# Proposal

## Why

Dual-slot wiring already separates per-ARC sync from optional catalog finalize, but both slots still share one
`ArcStore` ABC. Cross-role no-ops (`create_or_update` stubs on the catalog backend; default no-op `finalize` on per-ARC)
exist only to satisfy that shared type. Discussion #518 decided Split-ports; #615 is the deferred typing cleanup after
#517 shipped dual config/runtime.

## What Changes

- Introduce a small shared base for lifecycle (health / shutdown / tracer / shared errors) with **no** role ops.
- Narrow `ArcStore` to per-ARC persistence used by `GitRepo` (`create_or_update`, `get`, `delete`, `exists`, plus
  inherited lifecycle).
- Add `ConsolidatedArcStore` for catalog finalize / catalog health / catalog shutdown only (`ConsolidatedGitArcStore`
  implements it).
- Type factory, `ArcManager`, health, and worker wiring so `arc_store` is `ArcStore` and `consolidated_store` is
  `ConsolidatedArcStore | None` (no shared role ABC on both slots).
- Remove cross-role no-ops that only existed for the single ABC.
- Update OpenSpec `arc-store` so the port split matches role-based operations already specified.

**Non-goals:** peer array of equal stores; cross-store failure-policy framework; module renames beyond what typing
requires; offline filesystem stand-in changes unless it subclasses the product ABC; GitlabApi (already gone).

## Capabilities

### New Capabilities

_None — port split stays under existing `arc-store`._

### Modified Capabilities

- `arc-store`: Replace “optional finalize on ArcStore” / per-ARC finalize no-op contract with distinct `ArcStore` vs
  `ConsolidatedArcStore` ports on a shared lifecycle base; tighten dual-slot typing and role-based call-site
  requirements; drop scenarios that require invoking `finalize` on the per-ARC port.

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/` (`__init__.py`, `git_repo/`, `consolidated_git/`), factory /
  resolution, `ArcManager` / `BusinessLogic`, health checks, unit tests (`test_arc_store.py` and factory/wiring
  coverage).
- Specs: `openspec/specs/arc-store/` (delta in this change).
- HTTP / client contracts: unchanged (roles already separated at call sites).
- Issue: #615 (Fixes on draft PR after apply + commits).
