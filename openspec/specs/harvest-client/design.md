# Harvest Client Design

## Module Overview

`ApiClient` orchestrates the harvest lifecycle. `HarvestResult`,
`HarvestStatistics`, `HarvestError`, and `HarvestErrorType` are stable public
models for harvester processes.

```text
harvester
└─→ ApiClient.harvest_arcs(rdi, arcs)
    ├─→ create_harvest → HarvestResult (RUNNING)
    ├─→ _submit_arcs_parallel
    │   ├─→ client-side duplicate check → HarvestError(DUPLICATE)
    │   └─→ POST /v3/harvests/{id}/arcs
    │       └─→ HarvestError(SUBMISSION_FAILED) on item failure
    └─→ complete_harvest → HarvestResult (COMPLETED)
        └─→ merge client errors into HarvestResult.errors
```

## Design Decisions

### Typed public result models

`HarvestStatistics` is a Pydantic model rather than a dictionary because the
server's statistics fields and types are stable. `HarvestError` remains a
client-facing model independent of server models, allowing the client to
populate errors now and to parse server-persisted errors later without changing
the consumer interface.

`HarvestError.arc_id` is nullable. This represents errors that cannot be tied
to a specific ARC without introducing an empty-string sentinel.

### Compatibility with server-side error persistence

Until the server persists per-item errors, `harvest_arcs()` collects errors
from parallel submission and merges them into the completed response with
`model_copy(update=...)`. The merge is additive so future server-provided
errors are preserved. This compatibility boundary relates to the
`harvest-arc-upload` contract.

### Duplicate and retry boundaries

The client detects intra-batch duplicate identifiers before requests. The
server remains responsible for harvest-local idempotency: an identical retry
returns success while same-identifier differing content conflicts. See
`harvest-arc-upload`.

Because standalone and harvest-scoped ARC POST endpoints are idempotent for an
identical body, the client retries connection failures and `502`, `503`, and
`504` responses only for those endpoints. It does not retry harvest creation
or completion, and it preserves `409` as a conflict.

### Failure isolation

An item-level rejection does not prevent other valid ARCs from being submitted.
Authentication and invalid harvest-state failures are fatal: remaining tasks
are cancelled, the harvest is marked failed, and the original exception is
propagated. The server lifecycle transition is defined by `harvest-arc-upload`
and `arc-manager`.
