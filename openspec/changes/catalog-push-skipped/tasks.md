# Tasks

## 1. Event type + finalize wiring

- [ ] 1.1 Add `CATALOG_PUSH_SKIPPED` to `CatalogPushEventType` and update harvest document field description
- [ ] 1.2 In `finalize_catalog`, choose SUCCESS vs SKIPPED from `outcome.pushed`; keep shared message helper (neutral
      name) including skip summaries for both types

## 2. Tests

- [ ] 2.1 Unit test: `pushed=True` → `CATALOG_PUSH_SUCCESS`
- [ ] 2.2 Unit test: `pushed=False` → `CATALOG_PUSH_SKIPPED` with unchanged message
- [ ] 2.3 Adjust existing harvest-document / partial-skip tests that assume SUCCESS for every finalize success
- [ ] 2.4 Run focused `uv run pytest` on affected unit modules

## 3. Verify

- [ ] 3.1 `openspec validate catalog-push-skipped` (or project equivalent) passes
