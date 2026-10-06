# Design

## Context

See proposal.md — Why. Feature PRs already keep product-local `detect-changes` and pass `skip` into Devinfra
`reusable-code-quality` / local check. Helm release/pre-release callers already pass
`chart_dir: helmchart/fairagro-advanced-middleware-api-chart`. Devinfra `reusable-helm-lint.yml@main` accepts
`chart_dir`, `skip`, and `run_template` (default true). `docs/ci.md` already documents the intended Feature-PR snippet.

## Goals / Non-Goals

**Goals:**

- Orthogonal `code` vs `helm` path filters on the Feature PR workflow.
- Call the shared Helm lint reusable with this product’s chart directory.
- Keep chart-only PRs off the Docker build/check path.

**Non-Goals:**

- Extra template overlays (`helmchart/test_deploy/*`).
- Changing required GitHub check **names**.
- Widening the `code` filter to include charts.

## Decisions

### D1: Separate `helm` detect-changes output

`dorny/paths-filter` exposes `helm` for `helmchart/**` and leaves `code` without chart paths.

**Reason:** Putting charts only in `code` starts Docker/CQ without linting charts. A second output matches the
reusable’s `skip` contract and the locked routing on #206.

**Alternative considered:** Add `helmchart/**` to `code` only — rejected in issue comments.

### D2: Call `reusable-helm-lint.yml@main` with product `chart_dir`

`chart_dir: helmchart/fairagro-advanced-middleware-api-chart`, `skip` when `outputs.helm != 'true'`, leave
`run_template` at default (`true`).

**Reason:** Same chart root as Helm release callers; CLI version comes from caller `versions.env` (`HELM_VERSION`).
Default template smoke uses chart default values, which is the reusable’s fleet contract.

**Alternative considered:** Product-local `helm lint` job — duplicates Devinfra #288.

### D3: Helm lint is not a required branch-protection name in this slice

Required statuses stay `Container Structure Tests` and `Code Quality Check`. Helm lint still runs and can fail the
workflow; it is not added to `Define required checks`.

**Reason:** Locked explore option A; branch-protection edits are out of band.

### D4: Keep `build` job `if:` on `code`

`reusable-build` in this product still uses job-level `if: outputs.code == 'true'` rather than a `skip` input. Helm
filter does not change that.

**Reason:** Smallest caller delta; chart-only PRs already skip the build job.

## Risks / Trade-offs

- [Chart lint uses default values, not `test_deploy` overlays] → Mitigation: follow-up if mTLS/HTTPRoute templates need
  CI smoke; not this MVP.
- [Helm lint not required in branch protection] → Mitigation: the job still fails the Feature PR workflow when charts
  change and lint fails; owners can add the check name later.
- [Reusable `@main` moves] → Mitigation: same pin policy as other Feature-PR Helm/Docker callers except the existing
  code-quality SHA pin.

## Migration Plan

Merge the Feature PR workflow change. No runtime deploy. Rollback is revert of the workflow file.
