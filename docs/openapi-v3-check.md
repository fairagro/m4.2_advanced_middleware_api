# HTTP /v3 OpenAPI breaking-diff check

Product-local gate for [#651](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/651). (Fleet
[`docs/quality.md`](quality.md) is synced from Devinfra and must not be hand-edited for this.)

## What it does

`scripts/check-openapi-v3.sh` generates OpenAPI from the production FastAPI app on **HEAD** and on `main` (`origin/main`
in CI), keeps only paths under `/v3`, and runs [oasdiff](https://github.com/oasdiff/oasdiff) `breaking --fail-on ERR`.
There is no committed `openapi.json` — the document is always derived from `app.openapi()`.

| `/v3` OpenAPI vs `main` | Conventional Commit on `main..HEAD`                          | Result   |
| ----------------------- | ------------------------------------------------------------ | -------- |
| Breaking                | missing `type!:` / `type(scope)!:` and no `BREAKING CHANGE:` | **fail** |
| Breaking                | at least one commit declares breaking                        | **pass** |
| Non-breaking only       | (any)                                                        | **pass** |

Changes outside `/v3` (for example `/v2`) do not fail this gate. Public Python library surface is gated separately
([#570](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/570),
[`api-surface-check.md`](api-surface-check.md)). CouchDB document shapes remain
[#652](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/652).

## How to run

```bash
./scripts/install-oasdiff.sh              # pin OASDIFF_VERSION=1.39.0 by default
export PATH="${HOME}/.local/bin:${PATH}"
./scripts/check-openapi-v3.sh             # base: origin/main, else main
./scripts/check-openapi-v3.sh --base main
bash scripts/tests/test_check_openapi_v3.sh
```

Export only (filtered JSON):

```bash
uv run python scripts/export_openapi_v3.py -o /tmp/openapi-v3.json
```

Feature PRs run the same check in the **OpenAPI /v3** job (`.github/workflows/feature-pull-request.yml`).

## Agents / review

Failures are **toolchain-owned** (same class as Ruff/mypy / the griffe API surface gate). Do not re-litigate in
`/review-fixer` as a nit: either revert the `/v3` contract break or add a proper breaking Conventional Commit on the
branch.
