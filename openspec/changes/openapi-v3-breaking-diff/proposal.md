# Proposal

## Why

HTTP `/v3` is a user-facing contract. The griffe gate (#570) covers only the published Python library surface and
explicitly leaves OpenAPI out of scope. Silent breaking changes to paths, methods, required fields, or response schemas
can ship without a `!:` / `BREAKING CHANGE:` marker. A product-local OpenAPI breaking-diff vs `main` closes that gap for
#651.

## What Changes

- Add a product-local gate that generates OpenAPI from the production FastAPI app on tip and on `main` (no committed
  `openapi.json`)
- Restrict the comparison to `/v3/**` paths (filter before diff)
- Fail only on **breaking** changes per `oasdiff` (or equivalent); additive / non-breaking stays green
- Mirror the griffe escape hatch: undeclared breaking fails; declared via Conventional Commits (`type!:` /
  `BREAKING CHANGE:`) passes (**B2**)
- Wire the check into feature PR CI (alongside the API Surface job) and document a local script entrypoint
- Keep Devinfra fleet packaging out of scope until a second product needs the same pattern; CouchDB shapes remain #652

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `ci-cd`: Require an HTTP `/v3` OpenAPI breaking-diff gate on code PRs / local entrypoint, synced to Conventional
  Commit breaking markers (sibling to the existing public Python API surface requirement)

## Impact

- New scripts under `scripts/` (export filtered OpenAPI; run oasdiff; reuse commit-marker detection pattern from
  `check_api_surface.py`)
- CI: `.github/workflows/feature-pull-request.yml` (new job or step)
- Docs: product-local note (e.g. `docs/openapi-v3-check.md`) + cross-link from `docs/api-surface-check.md` /
  `docs/surface-quality-bar.md`; do not hand-edit synced `docs/quality.md`
- Tooling pin for `oasdiff` (binary or container); no runtime API behaviour change
- Issue: #651; related #570 (done), #652 (CouchDB, separate)
