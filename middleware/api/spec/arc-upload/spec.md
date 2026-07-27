# Standalone ARC Upload

**Scope:** HTTP API contract for `POST /v3/arcs`. A client submits a single ARC
outside of any harvest run. The `rdi` is provided explicitly in the request body.
Processing is delegated to `arc-manager/`.

This endpoint is **safe to retry** after transport failures for the same
`(identifier, rdi)` key: re-submission never creates a second document
(content-hash idempotency in `arc-manager/`). Unlike harvest-context upload,
a later call with **different** content for the same identifier is an update
(`UPDATED`), not a `409`.

## Requirements

- [ ] Accept a JSON request body conforming to `CreateArcRequest` containing
      `rdi` and `arc` as a `RoCratePayload` (see `arc-manager/` RoCrate wire
      contract).
- [ ] Validate that `rdi` is known to the deployment and authorized for this
      client; return `400` if the RDI is not recognized, `403` if not authorized.
- [ ] Delegate to the ARC ingestion pipeline (see `arc-manager/`)
      without a harvest context.
- [ ] On success (including an idempotent re-submission of identical content),
      fetch the updated ARC metadata from the document store and return an
      `ArcResponse` containing `client_id`, `arc_id`, `status`, `metadata`
      (hash, timestamps), and the current event log with HTTP `200`.
- [ ] Apply HTTP status mapping per `arc-manager/` HTTP caller contract.

## Edge Cases

`rdi` not in deployment `known_rdis` → `400` before calling business logic.

`rdi` known but not authorized for this client → `403` before calling business logic.

Same identifier re-submitted with identical content → `200` / `UPDATED`; no
second document; no second background sync.

Same identifier re-submitted with different content → `200` / `UPDATED`;
existing document replaced; background sync scheduled.

For RO-Crate validation failures, arctrl parse failures in the worker, and
generic pipeline errors, see `arc-manager/` edge cases and HTTP caller contract.
