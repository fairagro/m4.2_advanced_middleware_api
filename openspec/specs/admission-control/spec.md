# Request Admission Control

## Purpose

Admission control caps concurrent in-flight request handling within one API process. At capacity it returns a visible,
logged `503 Service Unavailable` with `Retry-After`, rather than allowing surplus requests to fail as transport
`ConnectError`s.

## Requirements

### Requirement: Enforce configurable process-local admission

The API process SHALL enforce a configurable maximum of concurrent in-flight requests. It MUST acquire a slot before
route handling and release it after response completion, including error responses; when at capacity it MUST return
`503` without running the handler. The limit SHALL be disabled when unset or non-positive.

#### Scenario: Reject at capacity

- **GIVEN** the in-flight count equals the configured maximum
- **WHEN** a non-exempt request arrives
- **THEN** it receives `503` and no business logic runs

#### Scenario: Release a failed request slot

- **GIVEN** a handler has acquired an admission slot
- **WHEN** the handler raises an error
- **THEN** the slot is released and a subsequent request may be admitted

#### Scenario: Leave legacy behavior enabled by default

- **GIVEN** the maximum is unset or less than or equal to zero
- **WHEN** requests arrive
- **THEN** no admission limiting occurs

### Requirement: Signal and log overload

Every admission-rejected response SHALL include `Retry-After` with a positive integer selected uniformly from `1`
through the configured inclusive upper bound. The system MUST log each rejection at warning level with the configured
limit and current in-flight count.

#### Scenario: Return jittered retry information

- **GIVEN** an admission rejection
- **WHEN** the response is created
- **THEN** it has `503 Service Unavailable` and a `Retry-After` delay in the configured range

### Requirement: Exempt probes and cover all other routes

The limiter SHALL exempt liveness, readiness, and health paths, which MUST neither consume a slot nor receive a
limiter-generated `503`. It MUST apply to every other HTTP method and API version, including ARC upload POSTs.

#### Scenario: Serve a probe at capacity

- **GIVEN** the process is at capacity
- **WHEN** a request targets an exempt probe path
- **THEN** it is handled normally without consuming a slot

#### Scenario: Limit ARC upload traffic

- **GIVEN** the process is at capacity
- **WHEN** an ARC upload POST arrives
- **THEN** it receives the admission `503`

### Requirement: Keep limits per process

The system SHALL maintain admission counts independently in every API process and MUST NOT use a cluster-wide shared
counter. Retrying a rejected idempotent ARC POST with an identical body SHALL remain safe as defined in `arc-upload/`
and `harvest-arc-upload/`.

#### Scenario: Serve multiple replicas

- **GIVEN** multiple API replicas
- **WHEN** each receives traffic
- **THEN** each independently applies its configured concurrency limit
