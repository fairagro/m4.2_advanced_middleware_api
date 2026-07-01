# Harvest-Context ARC Upload

**Scope:** HTTP API contract for `POST /v3/harvests/{harvest_id}/arcs`. A client
submits an ARC as part of an ongoing harvest run. The `rdi` is **not** in the
request body; it is resolved from the harvest document. Processing is delegated
to `arc-manager/`; harvest statistics tracking is part of that layer.

## Requirements

- [ ] Accept `harvest_id` as a path parameter and a JSON request body conforming
      to `SubmitHarvestArcRequest` containing `arc` as a `RoCratePayload` but
      **not** `rdi` (see `arc-manager/` RoCrate wire contract).
- [ ] Fetch the harvest document by `harvest_id`; return `404` if it does not exist.
- [ ] Resolve `rdi` from the harvest document.
- [ ] Validate that the resolved `rdi` is known to the deployment and authorized
      for this client; return `400` if not recognized, `403` if not authorized.
- [ ] Delegate to the ARC ingestion pipeline (see `arc-manager/`)
      with the resolved `rdi` and `harvest_id`.
- [ ] On success, fetch the updated ARC metadata from the document store and
      return an `ArcResponse` containing `client_id`, `arc_id`, `status`,
      `metadata` (hash, timestamps), and the current event log.
- [ ] Apply HTTP status mapping per `arc-manager/` HTTP caller contract.

## Edge Cases

`harvest_id` not found → `404` before calling business logic; `rdi` is never resolved.

Resolved `rdi` not in deployment `known_rdis` → `400`.

Resolved `rdi` known but not authorized for this client → `403`.

Same ARC submitted twice in one harvest → `409 Conflict` (`DuplicateArcInHarvestError`).

For RO-Crate validation failures, arctrl parse failures in the worker, metadata
fetch failures, and generic pipeline errors, see `arc-manager/` edge cases and
HTTP caller contract.
