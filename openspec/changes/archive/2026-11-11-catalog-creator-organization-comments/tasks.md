# Tasks

## 1. Materialize Creator Organization Comments

- [x] 1.1 In `catalog_materialize.py`, detect Comment names `Creator Organization` / `Creator Organization URL`
      (casefold), split `text` on `; `, pair by index, and build `Organization` objects (`@type`, `name`, optional
      `url`; strip fragment ids) — verify with a focused unit test that org-only Comments become `creator` Organizations
      and are removed from opaque `comment`
- [x] 1.2 Merge those Organizations into Dataset `creator` **after** Person materialization, preserving existing Persons
      and appending Orgs (single object vs list normalization consistent with Person lists) — verify with a unit test
      that Person + Organization both appear on `creator`
- [x] 1.3 Cover semicolon-joined multi-org + parallel URL pairing and URL-optional second org in
      `test_catalog_materialize.py` — verify
      `uv run pytest middleware/api/tests/unit/test_catalog_materialize.py -v --no-cov` passes; run ruff format/check on
      touched files

## Workflow follow-up

- Draft PR with `Fixes #586` after real commits exist ahead of `main`
- Archive this change after merge-ready implementation (`/opsx-archive` / issue-fixer last `go`)
