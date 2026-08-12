# Harvest Client — Delta

## ADDED Requirements

### Requirement: Send Idempotency-Key on harvest create

When creating a harvest, the client MUST send a non-empty `Idempotency-Key`
request header. The key MUST be generated once per logical create attempt and
MUST be reused for every transport retry of that same attempt. A later distinct
`create_harvest` call MUST use a different key.

#### Scenario: First create attempt includes a key

- **GIVEN** the caller starts a new harvest through the client
- **WHEN** the client issues `POST /v3/harvests`
- **THEN** the request includes a non-empty `Idempotency-Key` header

#### Scenario: Retries reuse the same key

- **GIVEN** a create attempt whose first transport attempt failed before a
  definitive response
- **WHEN** the client retries that create
- **THEN** it reuses the same `Idempotency-Key` as the failed attempt

## MODIFIED Requirements

### Requirement: Retry only idempotent ARC transport failures

The client MUST retry connection failures and transient `502`, `503`, or `504`
responses for `POST /v3/arcs` and `POST /v3/harvests/{harvest_id}/arcs`.
The client MUST also retry connection failures and those same transient status
codes for `POST /v3/harvests` when it sent an `Idempotency-Key` on that create,
reusing the key. It MUST NOT retry harvest completion POSTs or harvest create
requests that omit an `Idempotency-Key`, and MUST treat `409` conflicting ARC
content as a conflict rather than success. A `409` from keyed harvest create
(incompatible body reuse) MUST NOT be retried.

#### Scenario: Retry a transient harvest-scoped ARC submission failure

- **GIVEN** a harvest-scoped ARC POST receives a transient gateway failure
- **WHEN** the client retries it with the identical request body
- **THEN** the retry is safe because the endpoint is idempotent

#### Scenario: Retry keyed harvest create after ConnectError

- **GIVEN** `POST /v3/harvests` was sent with an `Idempotency-Key` and fails
  with a connection error before an HTTP response
- **WHEN** retries remain
- **THEN** the client retries the same create with the same key and body

#### Scenario: Do not retry harvest completion

- **GIVEN** a harvest completion request fails with a connection error
- **WHEN** the client handles the failure
- **THEN** it does not retry the completion POST

#### Scenario: Receive conflicting ARC content for an existing identifier

- **GIVEN** the server responds `409` for differing content with the same
  harvest-local ARC identifier
- **WHEN** the client handles the response
- **THEN** it does not treat the response as a successful retry
