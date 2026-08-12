# Harvest Create Idempotency-Key — Design

## Context

See proposal.md for motivation
([#305](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/305)).

Today `POST /v3/harvests` always allocates `harvest-{uuid}` in
`DocumentStore.create_harvest`. The API client treats only ARC POSTs as
retryable because create/complete are not server-idempotent. CouchDB remains the
persistence layer; uniqueness must work across concurrent API replicas without a
shared in-memory lock.

## Goals / Non-Goals

**Goals:**

- Additive wire contract: optional `Idempotency-Key` on create.
- Safe client retries for keyed create after ConnectError / 502–504.
- Single harvest document per `(client_id, key)` under concurrency.

**Non-Goals:**

- Mandatory keys or a new API version.
- Idempotency for complete / PATCH status transitions.
- Relying on `list_harvests` / #242 heuristics to recover a lost create
  response.

## Decisions

1. **Use the `Idempotency-Key` HTTP header (not a body field)**
   Reason: industry-standard, keeps `CreateHarvestRequest` unchanged, easy for
   proxies to log.
   Alternative considered: optional JSON field — rejected to avoid schema churn
   and mixed locations.

2. **Scope keys by authenticated `client_id`**
   Reason: prevents cross-tenant key collisions; matches harvest ownership.
   Require `client_id` when a key is present (`400` otherwise).
   Alternative: global key namespace — rejected (weak keys could collide across
   clients).

3. **Body compatibility = `rdi` + `expected_datasets` equality**
   Reason: those are the only create inputs that define the harvest; mismatched
   reuse is a client bug → `409`.
   Alternative: ignore `expected_datasets` on replay — rejected (progress
   denominator would silently diverge).

4. **Persist via a dedicated CouchDB index document**
   Document id pattern: `harvest-idempotency:{client_id}:{key}` (or a stable
   hash of the key if length/charset is unsafe for `_id`).
   Document body stores `harvest_id`, `rdi`, `expected_datasets`, and optional
   timestamps.
   First writer creates the harvest, then puts the index doc; on `_id` conflict,
   load the winner’s harvest and apply replay/409 rules.
   Reason: CouchDB document-create conflict gives cluster-safe uniqueness
   without a unique Mango index.
   Alternative: field on `HarvestDocument` + query — race-prone under concurrent
   creates.
   Alternative: use the key as the harvest `_id` — **BREAKING** / couples public
   harvest ids to client keys.

5. **Keep harvest `_id` as `harvest-{uuid}`**
   Reason: preserves existing ID format and clients that already store harvest
   ids.

6. **Response status stays `200` for create and replay**
   Reason: current create already returns 200; switching first create to 201
   would be a soft break for strict clients.
   Optional additive header `Idempotent-Replayed: true` on replay only.

7. **ApiClient may send a UUID4 key only when mTLS cert+key are configured**
   Reason: the wire header stays optional (backward compatible). Keyed create
   needs authenticated `client_id`; without certificates the API returns `400`
   for `Idempotency-Key`, so the client omits the header and MUST NOT retry
   create. With mTLS the library sends a key so create becomes retry-safe.
   Retry classification: treat keyed `POST /v3/harvests` like idempotent ARC
   POSTs for ConnectError and 502/503/504; still never retry completion or
   unkeyed create.

8. **Key retention**
   Keep the index document for the lifetime of the harvest document (no short
   TTL in v1).
   Reason: retries can occur minutes later; orphan cleanup of terminal harvests
   can delete the index later as a follow-up.

## Risks / Trade-offs

- **[Risk] Partial failure: harvest saved, index doc not yet written** →
  Mitigation: on index put failure, delete/compensate or retry index put; on
  next keyed create, if no index exists, a second harvest could appear — prefer
  “create index doc first in `pending` state then attach harvest_id” or
  transactional ordering documented in tasks with tests for the chosen order.
- **[Risk] Very long / weird keys as `_id`** → Mitigation: hash the key for
  `_id`, store raw key in the document body for debugging.
- **[Risk] Clients that manually POST without keys still fail hard on
  ConnectError** → Accepted; only library users gain retries.
- **[Trade-off] Index docs add storage** → Small vs harvest docs; acceptable.

## Migration Plan

1. Deploy API with optional header support (backward compatible).
2. Release api_client that sends keys and retries keyed create.
3. Roll harvesters to the new client when convenient — no coordinated cutover
   required.
4. Rollback: disable client key sending or ignore header server-side; existing
   harvests remain valid.

## Open Questions

None deferred — key hashing for `_id`, conflict semantics, and client always-on
keys are decided above.
