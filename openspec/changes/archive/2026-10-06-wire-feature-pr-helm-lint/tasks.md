# Tasks

## 1. Feature PR caller

- [x] 1.1 Add a `helm` detect-changes output for `helmchart/**` in `.github/workflows/feature-pull-request.yml` (do not
      add charts to `code`) and verify the job outputs both `code` and `helm`
- [x] 1.2 Add a `helm-lint` job that `needs: detect-changes`, calls
      `fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-helm-lint.yml@main` with
      `chart_dir: helmchart/fairagro-advanced-middleware-api-chart` and
      `skip: ${{ needs.detect-changes.outputs.helm != 'true' }}`, and verify the workflow file parses
      (`python3 -c 'import yaml; yaml.safe_load(open(".github/workflows/feature-pull-request.yml"))'`)

## 2. Notes alignment

- [x] 2.1 Confirm `docs/ci.md` Feature-PR example still matches the caller (`helm` filter + `chart_dir` + skip) and
      adjust only if the shipped YAML drifted from that snippet
