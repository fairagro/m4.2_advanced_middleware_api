# Proposal

## Why

Feature PRs never run Helm chart quality checks, so chart-only changes can merge without `helm lint`. Devinfra
[#288](https://github.com/fairagro/m4.2_middleware_devinfra/issues/288) now provides `reusable-helm-lint.yml` on `main`.
This product follow-up ([#206](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/206)) wires that reusable
with a **separate** chart path filter instead of stuffing `helmchart/**` into the Docker `code` bag.

## What Changes

- Feature-PR `detect-changes` gains a `helm` output for `helmchart/**` (orthogonal to `code`).
- Feature PRs call Devinfra `reusable-helm-lint.yml@main` with
  `chart_dir: helmchart/fairagro-advanced-middleware-api-chart` and `skip` when no chart paths changed.
- OpenSpec `ci-cd` requirements distinguish docs/spec-only PRs from Helm-only PRs: Helm-only MUST lint; MUST NOT start
  Docker build/check solely because charts changed.
- `docs/ci.md` / design notes stay aligned with the caller (already sketched; product workflow catches up).

Non-goals:

- Adding `helmchart/**` to the Docker `code` filter.
- Extra `helm template -f` overlays (`test_deploy` mTLS / HTTPRoute).
- Making `Helm Lint` a required branch-protection check name in this slice.
- Harvester (or other product) callers.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `ci-cd`: Pull-request change detection MUST classify chart paths separately from code. Helm-only PRs MUST run chart
  lint (and optional template smoke) and MUST NOT consume Docker build/check minutes. Docs/spec-only PRs still skip both
  Docker and Helm lint via no-op / skip.

## Impact

- `.github/workflows/feature-pull-request.yml` (product-local detect-changes + new `helm-lint` job).
- `openspec/specs/ci-cd/` (spec + design after archive).
- CI minutes: chart-only PRs run Helm CLI lint/template; code-only PRs skip Helm lint.
- No product Python/API/Helm chart template changes.
