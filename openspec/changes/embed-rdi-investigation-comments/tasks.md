# Tasks

## 1. Config registry

- [x] 1.1 Add a backward-compatible RDI entry model (string or `{id, description, url}`) on API and worker `Config`
      `known_rdis`; keep an identifier-list accessor for auth and GitLab topic validation; verify existing string-only
      YAML/fixtures still load via unit/config tests
- [x] 1.2 Update representative deploy/dev config samples (or comments) so operators see object-form entries; verify
      docs/samples mention description/URL fields

## 2. Ingest enrichment

- [x] 2.1 Implement RO-Crate `@graph` upsert for Investigation Comments `RDI` / `RDI Description` / `RDI URL` (stable
      `@id`s, root `comment` links, strip same-name duplicates) and `Comment[RDI]` conflict → semantic error mapped to
      `422`; verify pure unit tests on the helper (inject, overwrite description/URL, conflict, matching identity)
- [x] 2.2 Call enrichment in `ArcManager.create_or_update_arc` after `parse_rocrate` and before `store_arc` / Celery
      dispatch, using authorized `rdi` + registry lookup; verify manager/unit tests cover inject, conflict (no
      store/sync), and idempotent re-submit after enrichment
- [x] 2.3 Add a round-trip assertion that enriched JSON loaded with `ARC.from_rocrate_json_string` exposes the three
      Comments (name/value); verify via unit test

## 3. HTTP surface & quality

- [x] 3.1 Confirm standalone and harvest upload error mapping returns `422` for Comment conflict (reuse existing
      semantic-error mapping; add thin endpoint or manager tests if gaps); verify focused pytest passes
- [x] 3.2 Run `uv run ruff format --config ruff.toml` / `uv run ruff check --config ruff.toml` on touched files and
      focused `uv run pytest` for new/affected tests
