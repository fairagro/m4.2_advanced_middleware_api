# Tasks

## 1. Document-store identity gate

- [ ] 1.1 Add a dedicated identity-conflict exception (document-store and/or business-logic `ConflictError` subclass)
      distinct from `DuplicateArcError` / `DuplicateArcInHarvestError`; verify it is importable and subclasses the
      intended conflict base
- [ ] 1.2 In `store_arc`, when an existing `arc_{arc_id}` document is loaded, extract stored identifier from
      `arc_content` and compare strip-normalized identifier + `rdi` to the incoming pair; on mismatch raise the new
      conflict and skip save; verify unit tests cover mismatch refuse (no body write) and matching-identity continue
- [ ] 1.3 Ensure concurrent save retries re-check identity against the fresh document (same fail-closed rule); verify a
      unit/integration test covers retry/fresh-doc mismatch

## 2. Pipeline and HTTP mapping

- [ ] 2.1 Map the identity conflict through `ArcManager.create_or_update_arc` without scheduling Git sync; verify
      manager/unit tests assert conflict raised and no dispatch on mismatch
- [ ] 2.2 Map identity conflict to HTTP `409` on standalone `POST /v3/arcs` and harvest
      `POST /v3/harvests/{harvest_id}/arcs` with distinct detail from harvest content duplicates; verify API tests for
      both surfaces return `409` and leave stored docs unchanged

## 3. Regression and docs touch-ups

- [ ] 3.1 Keep existing harvest duplicate-content and identical-resubmit tests green; add/adjust coverage so identity
      mismatch is not confused with content duplicate; verify
      `uv run pytest middleware/api/tests/unit/ -k "arc or store or harvest"` (or the focused suite touched) passes
- [ ] 3.2 Note in code/docstrings or OpenAPI descriptions that identity `409` differs from harvest content `409`, and
      that NFC remains #537; verify no NFC / `calculate_arc_id` formula change landed in this PR
