# Tasks

## 1. OpenAPI export + /v3 filter

- [ ] 1.1 Add a Python helper that builds the production FastAPI app with in-memory dummy `Config` (no secrets /
      lifespan I/O) and returns `app.openapi()` as a dict — verify: `uv run python` one-liner / small unit test imports
      the helper and sees at least one `/v3` path
- [ ] 1.2 Add a `/v3` path filter (drop non-`/v3` paths from the OpenAPI dict; keep enough `components` for remaining
      refs or document why full components are retained) — verify: fixture with `/v2` + `/v3` paths yields only `/v3`
      after filter
- [ ] 1.3 Add a CLI/script entry that writes filtered OpenAPI JSON for the current tree to a given output path — verify:
      running the script produces valid JSON with `/v3` paths only

## 2. Breaking gate (oasdiff + Conventional Commits)

- [ ] 2.1 Pin/install `oasdiff` for local + CI (document version; binary download or container) — verify:
      `oasdiff     version` (or equivalent) prints the pinned version in the Dev Container / CI recipe
- [ ] 2.2 Implement tip-vs-base comparison: resolve base ref (`origin/main` then `main`, overridable), export filtered
      OpenAPI for HEAD and for base (worktree/checkout), run `oasdiff` in breaking-only mode — verify: scripted fixture
      or dry-run against identical tip/base exits 0
- [ ] 2.3 Reuse or share Conventional Commit breaking-marker detection with the griffe gate (**B2**): undeclared
      breaking → fail; declared `type!:` / `BREAKING CHANGE:` → pass; non-breaking → pass — verify: unit/shell tests
      covering the three outcomes (mirror `scripts/tests/test_check_api_surface.sh` style)
- [ ] 2.4 Expose `./scripts/check-openapi-v3.sh` as the documented local entrypoint — verify: script `--help` or bare
      run against current tree vs base completes with a clear pass/fail

## 3. CI + docs

- [ ] 3.1 Add a Feature PR workflow job (alongside `api-surface`) that runs
      `./scripts/check-openapi-v3.sh --base     origin/main` with oasdiff available — verify: workflow YAML references
      the script; job name is distinct in `feature-pull-request.yml`
- [ ] 3.2 Document the gate in `docs/openapi-v3-check.md` (behaviour table like `api-surface-check.md`, how to run,
      toolchain-owned for review) and cross-link from `docs/api-surface-check.md` + `docs/surface-quality-bar.md` —
      verify: docs mention #651, A1/C2/B2/D1 behaviour, and that synced `docs/quality.md` is untouched
- [ ] 3.3 Smoke: introduce a temporary undeclared `/v3` breaking change in a throwaway branch or fixture and confirm the
      gate fails; restore — verify: failing exit code observed once in local/CI recipe notes or automated fixture

## Workflow follow-up

- Draft PR after real commits (`m42-ai issue-start`)
- Archive this change on last `go` (`/opsx-archive`)
