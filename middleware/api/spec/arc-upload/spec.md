# Standalone ARC Upload

**Scope:** HTTP API contract for `POST /v3/arcs`. A client submits a single ARC
outside of any harvest run. The `rdi` is provided explicitly in the request body.
Processing is delegated to `arc-manager/`.

## Requirements

- [ ] Accept a JSON request body conforming to `CreateArcRequest` containing
      `rdi` and `arc` as a `RoCratePayload` (RO-Crate JSON with `@context`,
      `@graph`, root data entity `@id: "./"`, and non-empty `identifier`).
- [ ] Reject structurally invalid RO-Crate JSON during request parsing with
      `422 Unprocessable Entity` before calling business logic.
- [ ] Validate that `rdi` is in the list of authorized RDIs for this client;
      return `403` if not authorized.
- [ ] Delegate to the ARC ingestion pipeline (see `arc-manager/`)
      without a harvest context.
- [ ] On success, fetch the updated ARC metadata from the document store and
      return an `ArcResponse` containing `client_id`, `arc_id`, `status`,
      `metadata` (hash, timestamps), and the current event log.
- [ ] Return `500` when metadata cannot be retrieved after a successful store.
- [ ] Map `InvalidJsonSemanticError` to `422 Unprocessable Entity`.
- [ ] Map `BusinessLogicError` to `500 Internal Server Error`.

## Edge Cases

`rdi` not in authorized list → `403` before calling business logic.

ARC stored successfully but metadata fetch returns `None` → `500`; this indicates
an internal inconsistency.

Invalid RO-Crate JSON (missing `@context`, `@graph`, root data entity, or
non-empty `identifier`) → `422` from request validation.

Semantically invalid RO-Crate JSON accepted by the HTTP layer but rejected in
the worker queue → `422` via `InvalidJsonSemanticError` (defence in depth).
