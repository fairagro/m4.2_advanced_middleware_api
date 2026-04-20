# Harvest-Context ARC Upload

**Scope:** HTTP API contract for `POST /v3/harvests/{harvest_id}/arcs`. A client
submits an ARC as part of an ongoing harvest run. The `rdi` is **not** in the
request body; it is resolved from the harvest document. Processing is delegated
to `arc-manager/`; harvest statistics tracking is part of that layer.

## Requirements

- [ ] Accept `harvest_id` as a path parameter and a JSON request body conforming
      to `SubmitHarvestArcRequest` containing `arc` (RO-Crate JSON) but **not**
      `rdi`.
- [ ] Fetch the harvest document by `harvest_id`; return `404` if it does not exist.
- [ ] Resolve `rdi` from the harvest document.
- [ ] Validate that the resolved `rdi` is in the list of authorized RDIs for this
      client; return `403` if not authorized.
- [ ] Delegate to the ARC ingestion pipeline (see `arc-manager/`)
      with the resolved `rdi` and `harvest_id`.
- [ ] On success, fetch the updated ARC metadata from the document store and
      return an `ArcResponse` containing `client_id`, `arc_id`, `status`,
      `metadata` (hash, timestamps), and the current event log.
- [ ] Return `500` when metadata cannot be retrieved after a successful store.
- [ ] Map `InvalidJsonSemanticError` to `422 Unprocessable Entity`.
- [ ] Map `BusinessLogicError` to `500 Internal Server Error`.

## Edge Cases

`harvest_id` not found → `404` before calling business logic; `rdi` is never resolved.

Resolved `rdi` not authorized for this client → `403`.

ARC stored successfully but metadata fetch returns `None` → `500`; internal inconsistency.

Invalid RO-Crate JSON (missing `identifier`) → `422`.
