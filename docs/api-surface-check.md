# Public Python API surface check

Product-local gate for [#570](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/570). (Fleet
[`docs/quality.md`](quality.md) is synced from Devinfra and must not be hand-edited for this.)

## What it does

`scripts/check-api-surface.sh` uses [griffe](https://mkdocstrings.github.io/griffe/) to compare an **allowlisted**
public Python surface on `HEAD` against the same surface on `main` (`origin/main` in CI).

Allowlist: [`api-surface-allowlist.yaml`](../api-surface-allowlist.yaml) (`api_client`, selected `shared` modules).

| Surface vs `main` | Conventional Commit on `main..HEAD`                          | Result   |
| ----------------- | ------------------------------------------------------------ | -------- |
| Breaking          | missing `type!:` / `type(scope)!:` and no `BREAKING CHANGE:` | **fail** |
| Breaking          | at least one commit declares breaking                        | **pass** |
| Non-breaking only | (any)                                                        | **pass** |

HTTP OpenAPI and CouchDB document shapes are out of scope
([#651](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/651),
[#652](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/652)).

## How to run

```bash
./scripts/check-api-surface.sh              # base: origin/main, else main
./scripts/check-api-surface.sh --base main
bash scripts/tests/test_check_api_surface.sh
```

Feature PRs run the same script in the **API Surface** job (`.github/workflows/feature-pull-request.yml`).

## Agents / review

Failures are **toolchain-owned** (same class as Ruff/mypy CI). Do not re-litigate in `/review-fixer` as a nit: either
revert the break or add a proper breaking Conventional Commit on the branch.
