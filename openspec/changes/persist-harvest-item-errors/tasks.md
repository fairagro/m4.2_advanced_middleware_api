# Tasks

## 1. Models and persistence

- [x] 1.1 Add shared wire `HarvestError` / `HarvestErrorType` and `HarvestResponse.errors` (default `[]`); verify model
      import/tests for default empty list on legacy payloads
- [x] 1.2 Extend `HarvestDocument` with `errors: list[...] = []` and a document-store `append_harvest_error`
      (revision-safe); verify unit tests for legacy docs without the field and for append under conflict

## 2. Record on harvest upload conflicts

- [x] 2.1 On harvest-scoped `DuplicateArcInHarvestError` and `ArcIdentityMismatchError`, append the typed error then
      return existing `409`; verify API/unit tests that GET harvest shows the new error and identical `200` retry adds
      none
- [x] 2.2 Keep `statistics.errors` coherent with the list length (increment or recompute on append); verify the int
      field updates in the same tests

## 3. API client mapping

- [x] 3.1 Map server `errors` into `HarvestResult.errors` on harvest GET/complete paths used by `harvest_arcs`, keeping
      shim merge; verify unit tests for server-only errors and merged client+server lists

## 4. Specs already drafted

- [x] 4.1 Confirm OpenSpec deltas match the implemented behaviour (retry-safe `200` identical re-submit unchanged; shim
      retained; `409` only for true conflicts)
