# ARC Ingestion Pipeline

**Scope:** The shared business logic that accepts a validated ARC payload, persists
it quickly in the document store, and schedules an async GitLab sync. It is
triggered by two HTTP endpoints (`arc-upload/` and `harvest-arc-upload/`) and
must not assume it runs inside an HTTP request. The GitLab sync itself is
specified in `arc-store/`.

## Requirements

- [ ] Accept only a validated `RoCratePayload` (or raw dict validated to the
      same contract) with a non-empty root-dataset `identifier`.
- [ ] Persist the validated ARC in the document store.
- [ ] Report `CREATED` when no prior record exists for this ARC.
- [ ] Report `UPDATED` when a prior record exists and the content has changed.
- [ ] Report `UPDATED` (idempotent) when a prior record exists and the content is
      identical to what is already stored — without writing to the store again.
- [ ] Schedule a background GitLab sync if and only if the ARC is new or its
      content has changed.
- [ ] During GitLab sync, derive human-readable display metadata from the ARC
      payload (root dataset `name` and `description`, `identifier`, and `rdi`)
      and pass it to the Git store (see `arc-store/`).
- [ ] When a harvest context is provided, increment the harvest run's counters
      (new-ARC and changed-ARC) in the document store after persisting, regardless
      of whether a background sync was scheduled.
- [ ] Return an internal result to the caller containing the ARC identifier, its
      status (`CREATED` or `UPDATED`), a timestamp, the originating `rdi`, and
      the caller's `client_id`. The HTTP layer (see `arc-upload/` and
      `harvest-arc-upload/`) decides which of these fields to expose in the
      HTTP response.

## Edge Cases

Missing or invalid RO-Crate structure → `422` at the HTTP layer; worker path
re-validates queued payloads and maps failures to `InvalidJsonSemanticError`.

Unchanged ARC re-submitted → no write to the store, no background sync scheduled; harvest
counters still incremented (the ARC was received and processed).

Harvest counter increment fails → error propagates to the caller; the ARC is already
persisted at this point.

Unexpected error → wrapped and re-raised; caller maps this to `500`.
