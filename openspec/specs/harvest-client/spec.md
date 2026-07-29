# Harvest Client

## Purpose

The API client SHALL manage a harvest run from creation through ARC submission
and completion for harvester processes. It returns a typed, complete result
that includes server statistics and client-observed item errors.

## Requirements

### Requirement: Orchestrate the harvest lifecycle

The client MUST create a harvest for an RDI, submit every ARC from an
asynchronous source with bounded parallelism, complete the harvest, and return
the completed result as one operation.

#### Scenario: Complete a harvest from an asynchronous ARC source

- **GIVEN** an RDI and an asynchronous source of ARCs
- **WHEN** the caller invokes the harvest operation
- **THEN** the client creates the harvest, submits its ARCs with bounded
  parallelism, completes the harvest, and returns the completed result

### Requirement: Forward the expected dataset count

The client MUST accept an optional expected-dataset count when starting a
harvest and send it when creating the harvest so the server can track progress.

#### Scenario: Start a harvest with a progress denominator

- **GIVEN** an RDI and an expected-dataset count
- **WHEN** the client creates the harvest
- **THEN** the server receives the expected-dataset count for progress tracking

#### Scenario: Start a harvest without a progress denominator

- **GIVEN** an RDI and no expected-dataset count
- **WHEN** the client creates the harvest
- **THEN** the harvest is created without a progress denominator and its
  statistics report raw counts only

### Requirement: Return typed harvest statistics

The returned result MUST expose submitted, new, updated, unchanged, missing,
and optional expected-dataset counts as structured typed fields, not an opaque
mapping.

#### Scenario: Read completed harvest statistics

- **GIVEN** a completed harvest response
- **WHEN** the client returns its result
- **THEN** callers can access each required statistic as a typed field

### Requirement: Collect typed per-item errors

The result MUST include an errors list containing every item-level submission
error observed by the client. Each error MUST provide a category, a
human-readable message, an ISO 8601 occurrence timestamp, and an optional ARC
identifier.

#### Scenario: Return a successful harvest with no item errors

- **GIVEN** all ARC submissions succeed
- **WHEN** the completed result is returned
- **THEN** its errors list is empty

#### Scenario: Record an error without an extractable ARC identifier

- **GIVEN** an ARC has no extractable RO-Crate identifier and its submission
  produces an error

- **WHEN** the client records that error
- **THEN** the error has no ARC identifier

### Requirement: Detect duplicate identifiers before submission

The client MUST detect duplicate ARC identifiers within one batch before making
the duplicate request, skip the later ARC, and record a `duplicate` error. The
first ARC with that identifier MUST continue through normal submission.

#### Scenario: Skip the second ARC with a duplicate identifier

- **GIVEN** two submitted ARCs share an identifier
- **WHEN** the client processes the batch
- **THEN** it submits the first ARC, skips the second, and records a
  `duplicate` error for the second ARC

### Requirement: Continue after item-level submission failures

The client MUST classify a failed individual ARC submission as
`submission_failed`, record it, and continue submitting the remaining ARCs.

#### Scenario: One ARC is rejected while others remain valid

- **GIVEN** a harvest containing multiple ARCs
- **WHEN** one ARC submission fails with an item-level failure
- **THEN** the client records a `submission_failed` error and continues with
  the remaining ARCs

### Requirement: Fail catastrophic harvest errors

The client MUST treat catastrophic failures, including authentication failures
and invalid harvest state, as fatal: it MUST cancel remaining work, mark the
harvest as `FAILED`, and re-raise the error to the caller.

#### Scenario: Abort a harvest after authentication failure

- **GIVEN** ARC submission encounters an authentication failure
- **WHEN** the client classifies the failure as catastrophic
- **THEN** it cancels remaining tasks, transitions the harvest to `FAILED`, and
  propagates the exception

### Requirement: Retry only idempotent ARC transport failures

The client MUST retry connection failures and transient `502`, `503`, or `504`
responses for `POST /v3/arcs` and `POST /v3/harvests/{harvest_id}/arcs`.
It MUST NOT retry harvest creation or completion POSTs, and MUST treat `409`
conflicting ARC content as a conflict rather than success.

#### Scenario: Retry a transient harvest-scoped ARC submission failure

- **GIVEN** a harvest-scoped ARC POST receives a transient gateway failure
- **WHEN** the client retries it with the identical request body
- **THEN** the retry is safe because the endpoint is idempotent

#### Scenario: Receive conflicting ARC content for an existing identifier

- **GIVEN** the server responds `409` for differing content with the same
  harvest-local ARC identifier

- **WHEN** the client handles the response
- **THEN** it does not treat the response as a successful retry

<!-- Cross-References -->

- `harvest-arc-upload`: server-side harvest-local ARC identity, idempotency,
  and conflict behavior.

- `arc-manager`: shared ARC persistence and asynchronous synchronization
  behavior.
