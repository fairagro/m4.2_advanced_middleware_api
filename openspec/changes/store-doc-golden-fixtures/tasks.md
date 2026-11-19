# Tasks

## 1. Fixtures + tests

- [x] 1.1 Add `middleware/api/tests/fixtures/store_docs/README.md` describing allowlist (`HarvestDocument`,
      `ArcDocument`), add/retire rules, non-goals, and #590 Couch-era retire note — verify: file exists and names both
      types
- [x] 1.2 Add at least one older golden JSON fixture for harvest and one for ARC (envelope + minimal `arc_content` stub;
      reflect real historical gaps where practical, e.g. missing `client_id` / `last_changed`) — verify: files load as
      JSON and omit at least one field that tip models still accept via default/backfill
- [x] 1.3 Add unit tests that `HarvestDocument.model_validate` / `ArcDocument.model_validate` succeed for every
      supported fixture — verify: `uv run pytest` on the new test module passes

## 2. Docs / agent surface

- [x] 2.1 Cross-link from product surface docs if appropriate (e.g. brief note in `docs/surface-quality-bar.md` that
      store-doc fixtures are toolchain/test-owned) without editing synced `docs/quality.md` — verify: link reachable;
      synced quality.md untouched
- [x] 2.2 Smoke: temporarily break a tip model against a fixture (or a throwaway assertion) and confirm the new test
      would fail; restore — verify: observed failure once in local run notes or a negative fixture test that stays
      committed only if useful

## Workflow follow-up

- Draft PR after real commits (`m42-ai issue-start`)
- Archive this change on last `go` (`/opsx-archive`)
