# Catalog finalize skip observability — Proposal

## Why

Consolidated catalog finalize already does interim **partial push**
([#356](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/356)):
ARCs that fail extract/JSON-LD are skipped and remaining Datasets still
publish. Those skips are only visible in **worker logs**. Harvest
`CATALOG_PUSH_SUCCESS` still says only “Published…” / “unchanged”, so
operators cannot see from CouchDB harvest documents which ARCs were omitted.
Issue #356 acceptance asks for failures that are observable at harvest
(and/or per-ARC) level, not only an RDI-wide abort.

## What Changes

- Return a structured finalize **result** from `ArcStore.finalize` (pushed
  flag plus skip summary: count and `(arc_id, reason)` pairs), instead of a
  bare `bool`.
- On successful consolidated finalize, enrich the harvest
  `CATALOG_PUSH_SUCCESS` message with published/skipped counts and a bounded
  list of skipped `arc_id`s when any ARC was skipped.
- Keep all-fail → permanent error / `CATALOG_PUSH_FAILED` behaviour unchanged
  (already harvest-visible).
- Non-consolidated backends keep empty skip lists (no behaviour change for
  operators).

Non-goals: last-good retention; new `ArcEventType` / per-ARC CouchDB events;
new `CatalogPushEventType`; changing `HarvestCatalogEvent` schema fields
beyond `message` text; sparse-checkout; #340 lifecycle.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Successful consolidated catalog finalize MUST expose skip
  outcomes to the harvest catalog event path so partial-push omissions are
  harvest-visible (not only logged).
- `harvest-manager` (or harvest document / finalize orchestration as covered
  by existing harvest catalog-event behaviour): When recording
  `CATALOG_PUSH_SUCCESS` after a finalize that skipped one or more ARCs, the
  event message MUST include skip counts and skipped identities (bounded in
  the message).

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/__init__.py` (`finalize`
  return type); `consolidated_git/store.py`; `business_logic/arc_manager.py`
  (`finalize_catalog` event messages); unit tests for store finalize + harvest
  catalog events.
- Specs: `openspec/specs/arc-store/`, and harvest catalog-event wording under
  `openspec/specs/harvest-manager/` if that is where `CATALOG_PUSH_*` is
  specified (else arc-store only with cross-reference).
- Fixes the observability gap of
  [#356](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/356)
  interim AC; does not close last-good / #340 work.
- Branch: `explore/catalog-finalize-partial-publish-356` (rename to feature
  branch on apply if desired).
