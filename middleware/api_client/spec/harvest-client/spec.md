# Harvest Client

Manage the full lifecycle of a harvest run — creation, parallel ARC
submission, error collection, and finalization — on behalf of a harvester
process.  The client returns a typed result that captures both statistics
and per-item errors so harvesters can produce complete reports.

## Requirements

- [ ] Create a harvest run for a given RDI, submit all ARCs from an async
      source in bounded parallelism, and return the completed harvest result
      as a single operation.
- [ ] Accept an optional expected-dataset count at the start of a harvest to
      enable progress tracking on the server side.
- [ ] Return typed harvest statistics (submitted, new, updated, unchanged,
      missing counts, and optional expected-dataset count) as structured
      fields rather than an opaque mapping.
- [ ] Record per-item errors encountered during submission and include them
      in the returned harvest result.
- [ ] Classify each per-item error into one of the following categories:
      `duplicate` (two ARCs share the same identifier) or `submission_failed`
      (the server rejected or could not process the ARC).
- [ ] Each per-item error carries: the error category, a human-readable
      message, and an ISO 8601 timestamp of when the error occurred.
- [ ] Optionally associate a per-item error with an ARC identifier; errors
      that do not relate to a specific ARC (e.g. harvest-level failures) may
      omit the identifier.
- [ ] Detect duplicate ARC identifiers before submission and record them as
      `duplicate` errors; do not submit the duplicate.
- [ ] Skip individual ARC submission failures and continue the harvest with
      remaining items; record each failure as a `submission_failed` error.
- [ ] Abort the entire harvest on catastrophic errors (e.g. authentication
      failure, invalid harvest state) and mark the harvest as failed before
      propagating the exception to the caller.

## Edge Cases

ARC with no extractable RO-Crate identifier → submitted normally; any
resulting error records no ARC identifier (`null`).

Two ARCs share the same identifier → the second is skipped; a `duplicate`
error is recorded for it; the first continues to be submitted normally.

Catastrophic error during submission → remaining tasks are cancelled; the
harvest is transitioned to `FAILED`; the exception propagates to the caller.

No per-item errors → the returned result contains an empty errors list.

`expected_datasets` not provided → harvest is created without a progress
denominator; statistics show raw counts only.
