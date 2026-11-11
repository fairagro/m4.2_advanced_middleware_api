# Tasks

## 1. Materialize Landing Page → url

- [ ] 1.1 In `catalog_materialize.py`, map Comment name `landing page` (casefold): when Dataset lacks `url` and Comment
      `text` is non-empty, set `url` to `{"@id": text}`; always consume the Comment when the name matches; verify with a
      focused unit test that materialize sets `@id`-shaped `url` and drops the Comment
- [ ] 1.2 Add unit tests for: existing `url` preserved + Comment consumed; no Landing Page Comment → no invented `url`;
      preferably one compact survival assert (`url` term, not `schema:url`); verify
      `uv run pytest middleware/api/tests/unit/test_catalog_materialize.py -k landing -v --no-cov` passes

## 2. Quality

- [ ] 2.1 `uv run ruff format --config ruff.toml` / `uv run ruff check --config ruff.toml` on touched paths — clean
- [ ] 2.2
      `uv run pytest middleware/api/tests/unit/test_catalog_materialize.py middleware/api/tests/unit/test_catalog_jsonld.py -q --no-cov`
      — pass

## Workflow follow-up

- After apply + commits/push: draft PR with `Fixes #617`.
- Archive after review (`/opsx-archive` / issue-fixer last `go`).
