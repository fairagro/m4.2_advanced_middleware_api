# Harvest Create Idempotency-Key — Proposal

## Why

`POST /v3/harvests` is not safely retryable today: the harvest ID is
server-generated, and after a transport failure (e.g. `httpx.ConnectError`
before any HTTP response) the client cannot tell whether a harvest was created.
Blind retries risk orphan `RUNNING` harvests; omitting retries leaves transient
network blips as hard repository failures (see
[#305](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/305)).

## What Changes

- Accept an **optional** `Idempotency-Key` request header on `POST /v3/harvests`.
- When present, scope the key to at least `client_id` and reuse the existing
  harvest on compatible replay; conflicting body → `409`.
- When absent, preserve current create-always semantics (no **BREAKING** change).
- Persist the key so concurrent duplicate creates converge on one harvest
  document.
- Optionally emit an additive `Idempotent-Replayed` response header on replay.
- Update the API client to send a key on create and retry create on connection /
  selected transient failures while reusing that key.
- Update OpenSpec requirements in `harvest-manager` and `harvest-client` (and
  HTTP create contract if owned by a dedicated harvest upload/lifecycle domain).

## Capabilities

### New Capabilities

<!-- none — behaviour extends existing harvest create / client domains -->

### Modified Capabilities

- `harvest-manager`: Optional create-time idempotency key storage, lookup,
  conflict, and atomic uniqueness.
- `harvest-client`: Optional `Idempotency-Key` on create (send only when mTLS
  cert+key are configured); retry create only when a key was sent; without
  certificates omit key and refuse create retries; keep completion non-retryable
  unless separately specified.

## Impact

- API: `middleware/api/.../api/v3/harvests.py`, `HarvestManager`,
  `DocumentStore` / `HarvestDocument`, CouchDB indexes.
- Client: `middleware/api_client/.../api_client.py` retry classification and
  `create_harvest`.
- Specs: `openspec/specs/harvest-manager/`, `openspec/specs/harvest-client/`.
- Tests: API unit/system create-harvest coverage; client retry tests (replace
  “create must not retry” with key-aware behaviour).
- Non-goals: mandatory keys; idempotency for complete / status PATCH; using
  `list_harvests` (#242) as a substitute.
