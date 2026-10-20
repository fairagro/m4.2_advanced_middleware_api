# Tasks

## 1. Serialize the catalog to a file

- [ ] 1.1 Write the existing canonical catalog bytes to a temporary file under the cache directory and verify a unit
      test that those file bytes equal `serialize_catalog_file` for the same Dataset list
- [ ] 1.2 Publish by comparing and copying that file into the ephemeral clone, and verify consolidated-git unit tests
      still skip push when the remote file matches and push when it differs

## 2. Release datasets before clone

- [ ] 2.1 Drop the in-memory Dataset collection after serialization and before the Git clone starts, and verify a unit
      test that the collection is not retained when clone or publish begins
- [ ] 2.2 Keep the finalize outcome (push flag, Dataset count, skip list) and the all-ARC empty-wipe refusal, and verify
      the existing partial-push and all-fail unit tests pass

## 3. Cleanup and page-size note

- [ ] 3.1 Remove the serialized catalog file when finalize succeeds or when Git raises, and verify a unit test that the
      file is gone in both cases
- [ ] 3.2 State in the `catalog_list_page_size` field description that a lower value shrinks the CouchDB page of full
      ARC bodies, and verify the model default remains 500

## 4. Integration check

- [ ] 4.1 Run `uv run pytest middleware/api/tests/unit/test_consolidated_git_arc_store.py --no-cov` and
      `uv run ruff check --config ruff.toml` on the touched files, and verify both succeed
