# Harvest Manager — Delta

## ADDED Requirements

### Requirement: Optional create Idempotency-Key

`POST /v3/harvests` SHALL accept an optional `Idempotency-Key` request header.
When the header is absent, the system MUST create a new harvest run exactly as
today. When the header is present, it MUST be a non-empty string and the
request MUST carry an authenticated `client_id`; otherwise the system MUST
reject the request with `400 Bad Request`.

#### Scenario: Create without Idempotency-Key

- **GIVEN** a valid create body and no `Idempotency-Key` header
- **WHEN** `POST /v3/harvests` is processed
- **THEN** a new harvest document is created and returned

#### Scenario: Reject empty Idempotency-Key

- **GIVEN** a create request with an empty `Idempotency-Key` header
- **WHEN** `POST /v3/harvests` is processed
- **THEN** the response is `400 Bad Request` and no harvest is created

#### Scenario: Reject keyed create without client identity

- **GIVEN** a create request with a non-empty `Idempotency-Key` and no
  authenticated `client_id`
- **WHEN** `POST /v3/harvests` is processed
- **THEN** the response is `400 Bad Request` and no harvest is created

### Requirement: Replay compatible keyed creates

When `Idempotency-Key` is present and a harvest already exists for the same
`client_id` and key, and the request body is compatible with that harvest
(`rdi` equal and `expected_datasets` equal, including both unset), the system
SHALL return that existing harvest as `200` with the same response body shape
as a first-time create. It MUST NOT create a second harvest document. The
system MAY include the response header `Idempotent-Replayed: true` on such
replays.

#### Scenario: Replay after a lost create response

- **GIVEN** a harvest was created for client `C` with key `K` and body `B`
- **WHEN** the same client repeats `POST /v3/harvests` with header
  `Idempotency-Key: K` and body `B`
- **THEN** the response is `200` with the original harvest's identity and
  fields
- **AND** no additional harvest document exists for that key

### Requirement: Conflict on incompatible keyed reuse

When `Idempotency-Key` is present and a harvest already exists for the same
`client_id` and key, but the request body is incompatible (`rdi` or
`expected_datasets` differs), the system MUST respond with `409 Conflict` and
MUST NOT modify the existing harvest.

#### Scenario: Reuse key with a different RDI

- **GIVEN** a harvest exists for client `C` with key `K` and `rdi=a`
- **WHEN** the same client posts create with `Idempotency-Key: K` and `rdi=b`
- **THEN** the response is `409 Conflict`
- **AND** the existing harvest remains unchanged

### Requirement: Atomic uniqueness for keyed creates

Concurrent `POST /v3/harvests` requests that share the same `client_id` and
`Idempotency-Key` MUST converge on a single harvest document. Exactly one
create MUST persist; other concurrent attempts MUST observe that harvest as a
compatible replay or receive a transient failure that is safe to retry with
the same key.

#### Scenario: Two concurrent keyed creates

- **GIVEN** two overlapping create requests from the same client with the same
  non-empty `Idempotency-Key` and compatible bodies
- **WHEN** both are processed
- **THEN** exactly one harvest document is stored for that client and key
- **AND** both successful responses refer to that same harvest identity
