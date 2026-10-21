# Tasks

## 1. Config knob

- [x] 1.1 Add `max_catalog_event_log_size` to `CouchDBConfig` with default 100 and minimum 1, and verify a unit test
      that the model default is 100 and a value below 1 is rejected

## 2. Trim on append

- [x] 2.1 After appending a catalog event in `_apply_harvest_updates`, keep only the newest `max_catalog_event_log_size`
      entries, and verify a unit test that an append past the maximum drops the oldest event, keeps the appended event
      last, and leaves the list length equal to the maximum
- [x] 2.2 Leave an append under the maximum intact, and verify a unit test that every previous catalog event remains and
      the appended event is last
- [x] 2.3 Do not trim on a harvest update that does not append a catalog event, and verify a unit test that a
      status-only update keeps an over-maximum catalog-event list unchanged

## 3. Integration check

- [x] 3.1 Run `uv run pytest middleware/api/tests/unit/test_couchdb_store.py --no-cov` and
      `uv run ruff check --config ruff.toml` on the touched files, and verify both succeed
