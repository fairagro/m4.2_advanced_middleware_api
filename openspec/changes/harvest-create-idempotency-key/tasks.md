# Harvest Create Idempotency-Key — Tasks

## 1. Persistence model

- [x] 1.1 Add a CouchDB idempotency index document model (stores raw key,
  `client_id`, `harvest_id`, `rdi`, `expected_datasets`, status) with `_id`
  derived from a stable hash of `(client_id, key)`
- [x] 1.2 Implement DocumentStore helpers: put/get index doc, create harvest
  unchanged for unkeyed path, keyed create using claim-then-finalize ordering
  (create index as `pending`, create harvest, patch index with `harvest_id` /
  `committed`)
- [x] 1.3 On index `_id` conflict, load winner and return existing harvest or
  signal body conflict; never leave a second harvest linked to the same key

## 2. API / HarvestManager

- [x] 2.1 Extend `create_harvest` to accept optional `Idempotency-Key`; reject
  empty key or keyed create without `client_id` with `400`
- [x] 2.2 Wire `POST /v3/harvests` to read the header, invoke keyed/unkeyed
  paths, return `200` `HarvestResponse`, set `Idempotent-Replayed: true` on
  compatible replay, map incompatible reuse to `409`
- [x] 2.3 Map persistence conflict / ownership errors to existing HTTP error
  conventions without changing unkeyed behaviour

## 3. API client

- [x] 3.1 Generate a UUID4 `Idempotency-Key` inside `create_harvest` and send it
  on `POST /v3/harvests`
- [x] 3.2 Treat keyed `POST /v3/harvests` as retryable for ConnectError and
  `502`/`503`/`504`, reusing the same key across retries; keep completion
  non-retryable; do not retry create `409`
- [x] 3.3 Update/replace `test_create_harvest_network_error_not_retried` and add
  tests for key header presence, key reuse on retry, and successful retry after
  ConnectError

## 4. Tests and quality

- [x] 4.1 Add API unit/system tests: no header (legacy create), replay same
  key+body, `409` on body mismatch, `400` empty key / missing client, concurrent
  same-key creates → one harvest
- [x] 4.2 Run focused `uv run pytest` for api + api_client harvest/create/retry
  suites; run `uv run ruff format/check --config pyproject.toml middleware/` on
  touched code
