# Rate Limiting (ARC / harvest writes)

## Purpose

Per-client rate limiting protects harvest creation and ARC submission HTTP endpoints from flood abuse by a single
authenticated (or anonymous) caller. Limits are process-local, configurable, and distinct from process-wide concurrency
admission control. Exceeding a limit yields `429 Too Many Requests` with `Retry-After`.

## Requirements

### Requirement: Enforce configurable per-client rate limits on write POSTs

When rate limiting is enabled, the API process SHALL apply per-client request frequency limits to these methods and
paths only:

- `POST /v3/harvests` (harvest-create class)
- `POST /v3/harvests/{harvest_id}/arcs` (arc-submit class)
- `POST /v3/arcs` (arc-submit class)
- `POST /v2/arcs` (arc-submit class)

The limit key SHALL be the client certificate CN when present; when no client identity is available the key SHALL be the
literal `anonymous`. Clients SHALL NOT share buckets across different keys. Unlisted routes MUST NOT be rate-limited by
this capability. When rate limiting is disabled, these routes MUST behave as today with respect to rate limiting (no
limiter-generated `429`).

#### Scenario: Allow traffic under the limit

- **GIVEN** rate limiting is enabled and the client is under its class limit
- **WHEN** the client sends a listed write POST
- **THEN** the request proceeds to normal handling (subject to other middleware)

#### Scenario: Reject over-limit traffic

- **GIVEN** rate limiting is enabled and the client has exhausted its class limit for the current window
- **WHEN** the client sends another listed write POST for that class
- **THEN** the response is `429 Too Many Requests` and route business logic does not run

#### Scenario: Disable rate limiting

- **GIVEN** rate limiting is disabled
- **WHEN** clients send listed write POSTs
- **THEN** no limiter-generated `429` is returned

#### Scenario: Anonymous callers share one key

- **GIVEN** rate limiting is enabled and two requests have no client certificate identity
- **WHEN** both send listed write POSTs
- **THEN** both consume the same `anonymous` bucket for that limit class

### Requirement: Separate limit classes with configurable defaults

The harvest-create class and the arc-submit class SHALL have independently configurable integer limits expressed as
maximum requests per minute per client key. When rate limiting is enabled and a class limit is unset in config, the
system SHALL use **10** requests per minute for harvest-create and **60** requests per minute for arc-submit. A
non-positive configured class limit SHALL mean that class is unlimited while rate limiting remains enabled for other
classes that still have positive limits.

#### Scenario: Apply harvest-create default

- **GIVEN** rate limiting is enabled with default harvest-create limit
- **WHEN** a single client key sends more than 10 `POST /v3/harvests` within one minute
- **THEN** subsequent harvest-create requests for that key receive `429` until the window allows more

#### Scenario: Apply arc-submit default across ARC paths

- **GIVEN** rate limiting is enabled with default arc-submit limit
- **WHEN** a single client key sends a mix of `POST /v3/arcs`, `POST /v2/arcs`, and harvest-scoped ARC POSTs totaling
  more than 60 within one minute
- **THEN** subsequent arc-submit requests for that key receive `429` until the window allows more

#### Scenario: Unlimited class when non-positive

- **GIVEN** rate limiting is enabled and the harvest-create limit is configured as non-positive
- **WHEN** a client sends many `POST /v3/harvests`
- **THEN** harvest-create requests are not rejected by the rate limiter for that class

### Requirement: Signal retry with Retry-After on 429

Every rate-limit rejection SHALL use status `429 Too Many Requests` and MUST include a `Retry-After` header with a
positive integer number of seconds. The upper bound for that delay SHALL be configurable independently of admission
control’s `retry_after_seconds` unless the implementation documents a deliberate shared setting; the value MUST be at
least `1`.

#### Scenario: Return Retry-After on rejection

- **GIVEN** a rate-limit rejection
- **WHEN** the response is created
- **THEN** it has status `429` and a `Retry-After` header with a positive integer

### Requirement: Keep limits per process

The system SHALL maintain rate-limit state independently in every API process and MUST NOT require a shared cluster-wide
store (including Redis) for this capability.

#### Scenario: Independent replica budgets

- **GIVEN** multiple API replicas with rate limiting enabled
- **WHEN** the same client key sends listed write POSTs to different replicas
- **THEN** each replica applies its own per-process limits independently
