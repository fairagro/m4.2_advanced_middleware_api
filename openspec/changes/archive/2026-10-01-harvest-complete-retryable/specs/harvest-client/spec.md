# Harvest Client Delta

## MODIFIED Requirements

### Requirement: Retry only idempotent ARC transport failures

The client MUST retry connection failures and transient `502`, `503`, or `504` responses for `POST /v3/arcs` and
`POST /v3/harvests/{harvest_id}/arcs`. The client MUST also retry connection failures and those same transient status
codes for `POST /v3/harvests` when it sent an `Idempotency-Key` on that create, reusing the key. The client MUST retry
connection failures and those same transient status codes for harvest completion requests
(`POST /v3/harvests/{harvest_id}/complete`). It MUST NOT retry harvest create requests that omit an `Idempotency-Key`
(including creates without mTLS), and MUST treat `409` conflicting ARC content as a conflict rather than success. A
`409` from keyed harvest create (incompatible body reuse) MUST NOT be retried.

#### Scenario: Retry a transient harvest-scoped ARC submission failure

- **GIVEN** a harvest-scoped ARC POST receives a transient gateway failure
- **WHEN** the client retries it with the identical request body
- **THEN** the retry is safe because the endpoint is idempotent

#### Scenario: Retry keyed harvest create after ConnectError

- **GIVEN** `POST /v3/harvests` was sent with an `Idempotency-Key` and fails with a connection error before an HTTP
  response
- **WHEN** retries remain
- **THEN** the client retries the same create with the same key and body

#### Scenario: Do not retry unkeyed harvest create

- **GIVEN** `POST /v3/harvests` was sent without an `Idempotency-Key` and fails with a connection error
- **WHEN** the client handles the failure
- **THEN** it does not retry the create POST

#### Scenario: Do not retry harvest create without mTLS

- **GIVEN** the client has no client certificates configured
- **WHEN** `POST /v3/harvests` fails with a connection error
- **THEN** the client does not retry the create POST

#### Scenario: Retry harvest completion after ConnectError

- **GIVEN** a harvest completion request fails with a connection error before an HTTP response
- **WHEN** retries remain
- **THEN** the client retries the same completion request (completion is idempotent on the server)

#### Scenario: Receive conflicting ARC content for an existing identifier

- **GIVEN** the server responds `409` for differing content with the same harvest-local ARC identifier
- **WHEN** the client handles the response
- **THEN** it does not treat the response as a successful retry

## ADDED Requirements

### Requirement: Treat already-completed harvest as successful completion

When a harvest completion request fails (after retries are exhausted or the failure is not retryable), the client MUST
fetch the harvest by id. If the harvest status is already `COMPLETED`, the client MUST treat the completion as
successful and MUST NOT require a successful completion POST response. If the harvest is still `RUNNING`, the client
MUST surface the original completion failure. Other terminal statuses (`CANCELLED`, `FAILED`) MUST NOT be treated as
successful completion.

#### Scenario: Lost completion response recovers via GET

- **GIVEN** completion fails with a connection error after retries are exhausted
- **AND** a subsequent GET shows the harvest is `COMPLETED`
- **WHEN** the client applies completion defense
- **THEN** it treats completion as success

#### Scenario: Still-running harvest does not fake success

- **GIVEN** completion fails with a connection error after retries are exhausted
- **AND** a subsequent GET shows the harvest is still `RUNNING`
- **WHEN** the client applies completion defense
- **THEN** it surfaces the original completion failure
