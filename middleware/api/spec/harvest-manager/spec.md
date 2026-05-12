# Harvest Management

Track the lifecycle of a harvest run — creation, progress counting, and
finalization — and enforce client ownership of harvest resources.

## Requirements

- [ ] Create a new harvest run document in CouchDB and return its `harvest_id`.
- [ ] Associate the harvest run with a `client_id` and `rdi` at creation time.
- [ ] Accept an optional `expected_datasets` count at creation to enable progress tracking.
- [ ] Retrieve a harvest run document by `harvest_id`.
- [ ] Validate that the requesting `client_id` matches the `client_id` stored in
      the harvest document; raise `AccessDeniedError` on mismatch.
- [ ] Raise `ResourceNotFoundError` when a `harvest_id` does not exist in CouchDB.
- [ ] Increment per-harvest statistics (new-ARC counter and changed-ARC counter)
      via `increment_harvest_statistics` for each processed ARC.
- [ ] Finalize a harvest run, marking it complete and recording the final statistics.
- [ ] Transition a harvest run to a target terminal status (`COMPLETED`, `CANCELLED`,
      or `FAILED`) via an explicit state-transition operation.
- [ ] Enforce the transition guard: only a `RUNNING` harvest may transition to a
      terminal status; raise `ConflictError` otherwise.

## Edge Cases

`client_id` mismatch → raise `AccessDeniedError`; do not reveal the stored client ID in the error message.

`harvest_id` not found → raise `ResourceNotFoundError` with the harvest ID in the message.

`expected_datasets` not provided → harvest document is created without a progress denominator; progress reporting shows raw counts only.

Finalize called before all ARCs arrive → harvest is marked complete with whatever statistics are current; no enforcement of `expected_datasets`.

Transition called on a non-`RUNNING` harvest → raise `ConflictError` with the current status in the message.
