# Proposal

## Why

Catalog finalize currently appends `CATALOG_PUSH_SUCCESS` even when nothing was pushed (`CatalogFinalizeResult.pushed`
is false — “unchanged on remote”). That overloads SUCCESS for a no-op and is inconsistent with per-ARC
`GIT_PUSH_SKIPPED` (#313). Splitting the event type keeps metrics and filters honest without changing finalize
behaviour.

## What Changes

- Append `CATALOG_PUSH_SKIPPED` on the harvest `catalog_events` list when finalize returns `pushed=False`, keeping the
  existing unchanged / skip-summary message text
- Keep `CATALOG_PUSH_SUCCESS` only when a catalog commit/push actually ran (`pushed=True`)
- Leave `CATALOG_PUSH_FAILED` and partial-ARC-skip messaging on successful pushes unchanged
- Add unit tests for pushed vs skipped event typing

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `harvest-manager`: distinguish no-op catalog finalize (`CATALOG_PUSH_SKIPPED`) from a real catalog push
  (`CATALOG_PUSH_SUCCESS`)

## Impact

- Code: `CatalogPushEventType`, `ArcManager.finalize_catalog`, harvest document model field text, unit tests in
  `test_business_logic` / `test_harvest_document`
- Specs: `openspec/specs/harvest-manager/`
- No HTTP/`HarvestResponse` change (`catalog_events` remain document-only)
- Additive CouchDB enum value on harvest docs (forward-compatible for readers that ignore unknown types; strict enum
  clients that only know SUCCESS/FAILED may need the new member)
