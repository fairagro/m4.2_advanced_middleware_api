# Tasks

## 1. Specs & server assertion gaps

- [ ] 1.1 Confirm existing server COMPLETED replay + finalize re-enqueue tests cover Option A; add only if gaps
- [ ] 1.2 Keep harvest-manager delta aligned with byte-stable catalog no-op scenario (no Option B behaviour)

## 2. ApiClient retry + defense

- [ ] 2.1 Mark `POST …/complete` as retryable under the existing transient retry policy (same as idempotent ARC POSTs)
- [ ] 2.2 After failed completion (retries exhausted), GET harvest; if `COMPLETED` treat as success; if `RUNNING`
      surface original failure
- [ ] 2.3 Unit tests: ConnectError retries complete; exhausted retries + GET `COMPLETED` → success; GET still `RUNNING`
      → failure

## 3. Verify

- [ ] 3.1 Run focused `uv run pytest` on api_client (and any touched api) unit tests; ruff format/check on touched files
