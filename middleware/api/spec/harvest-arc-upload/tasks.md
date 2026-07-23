# Harvest-Context ARC Upload — Tasks (idempotent POST)

- [ ] Change document-store harvest duplicate check: raise `DuplicateArcError`
      only when the same identifier was already seen in this harvest **and**
      the content hash differs; identical content falls through as unchanged
      (`has_changes=False`).
- [ ] Update the concurrent `pre_save_validator` to the same
      identical-vs-conflicting rule (compare hash on the fresh document).
- [ ] Keep HTTP mapping: `DuplicateArcInHarvestError` → `409`; idempotent
      success → existing `200` + `ArcResponse` path.
- [ ] Update unit tests that currently expect `409` for identical re-submit
      (`test_v3_harvests`, `test_couchdb_store`) to expect success / unchanged.
- [ ] Add tests for same-identifier / different-content → `409` and for
      concurrent identical re-submit → no duplicate document.
- [ ] Enable api-client POST retries for this endpoint once the server
      contract is in place (see `harvest-client/`); treat only conflicting
      `409` as non-retryable item/harvest error, not identical re-submit.
