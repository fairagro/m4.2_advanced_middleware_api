# Harvest-Context ARC Upload

**Scope:** HTTP API contract for `POST /v3/harvests/{harvest_id}/arcs`. A client
submits an ARC as part of an ongoing harvest run. The `rdi` is **not** in the
request body; it is resolved from the harvest document. Processing is delegated
to `arc-manager/`; harvest statistics tracking is part of that layer.

This endpoint is **safe to retry** after transport failures (`ConnectError`,
lost response): re-submitting the same ARC identifier with the same content
within one harvest must not create a second object and must succeed with
`200` (see `arc-manager/` harvest idempotency rules).

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
- [ ] On success (including an idempotent re-submission of identical content),
      fetch the updated ARC metadata from the document store and return an
      `ArcResponse` containing `client_id`, `arc_id`, `status`, `metadata`
      (hash, timestamps), and the current event log with HTTP `200`.
- [ ] Apply HTTP status mapping per `arc-manager/` HTTP caller contract,
      including harvest-scoped conflict mapping.

## Edge Cases

`harvest_id` not found → `404` before calling business logic; `rdi` is never resolved.

Resolved `rdi` not in deployment `known_rdis` → `400`.

Resolved `rdi` known but not authorized for this client → `403`.

Same ARC identifier re-submitted in the same harvest with **identical** content
→ `200` with status `UPDATED` (idempotent); no second document; no second
background sync. Safe for client retries after `ConnectError` / lost responses.

Same ARC identifier re-submitted in the same harvest with **different** content
→ `409 Conflict` (`DuplicateArcInHarvestError`); existing document unchanged.

For RO-Crate validation failures, arctrl parse failures in the worker, metadata
fetch failures, and generic pipeline errors, see `arc-manager/` edge cases and
HTTP caller contract.
