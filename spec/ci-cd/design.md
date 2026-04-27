# CI/CD Workflows — Design

## Workflow Overview

```text
On PR → main:
    feature-pull-request.yml
        ├─→ reusable-code-quality.yml
        ├─→ reusable-build.yml        (push=false)
        └─→ reusable-check.yml

On workflow_dispatch (Pre Release, any branch):
    pre-release.yml
        ├─→ reusable-code-quality.yml
        ├─→ reusable-build.yml        (push=true)
        ├─→ reusable-check.yml
        └─→ reusable-release.yml      (no GitHub Release)
               ├─→ push-dockerhub     (independent)
               ├─→ push-ghcr          (independent)
               ├─→ publish-pypi       (TestPyPI, independent)
               └─→ create-release-tag

On workflow_dispatch (Release, main only):
    release.yml
        ├─→ reusable-code-quality.yml
        ├─→ reusable-build.yml        (push=true)
        ├─→ reusable-check.yml
        └─→ reusable-release.yml      (creates GitHub Release)
               ├─→ push-dockerhub     (independent)
               ├─→ push-ghcr          (independent)
               ├─→ publish-pypi       (PyPI, independent)
               ├─→ create-release-tag
               └─→ github-release     (runs if tag created, regardless of upload outcomes)

On workflow_dispatch (Helm Chart Release):
    helm-release.yml
        └─→ package + publish chart

On push feature/* or schedule:
    codeql.yml
        └─→ CodeQL analysis (Python + Actions)
```

## Reusable Workflows

| File | Purpose |
| --- | --- |
| `reusable-code-quality.yml` | Ruff, Pylint, MyPy, Bandit, pytest |
| `reusable-build.yml` | Version calc, Docker build, SBOM generation, Python package build |
| `reusable-check.yml` | Licence scan, Trivy vuln scan, container structure tests |
| `reusable-release.yml` | Independent upload jobs (DockerHub, GHCR, PyPI) + Git tag + GitHub Release |

## Key Decisions

1. **Bash for version calculation**
   — GitVersion (a .NET tool) was considered but rejected because it introduces
   a heavyweight external dependency. A short bash script that finds the latest
   semver tag in the appropriate namespace (`docker-v*`, `chart-v*`), parses it,
   and applies the bump handles this transparently with zero external dependencies.

2. **`YYYYMMDDhhmmss` as ordering prefix**
   — A fixed-length 14-character timestamp satisfies the spec's lexical monotone
   requirement because its fixed length guarantees that lexical sort equals
   chronological sort. The prefix is stripped from the human-readable GitHub
   Release name.

3. **Draft → Publish pattern for immutable releases**
   — The spec requires asset attachment even when repository release immutability
   is enabled. The only way to satisfy both constraints is to create the release
   as `draft: true` first (asset uploads are allowed on drafts), then finalize it
   with a separate `gh api PATCH draft=false` call. This applies to both
   `reusable-release.yml` and `helm-release.yml`.

4. **Feature branch releases always create a Git tag**
   — Even when no GitHub Release entry is produced, a Git tag is required so the
   version calculator always has a valid baseline for the next run. The suffix
   order `rc.{branch-label}.{run_number}` groups all builds from the same branch
   together and sorts them chronologically within that group.

5. **Transfer artifact pattern**
   — `reusable-build.yml` saves the Docker image and SBOM as GitHub Actions
   artifacts; downstream jobs (`reusable-check.yml`, `reusable-release.yml`)
   download them rather than rebuilding. This guarantees that the image that
   passed the check phase is byte-for-byte identical to the one released.

6. **Check phase: three independent job groups**
   — `licence-check` (Trivy licence scanner), `security-check` (Trivy vuln scan
   + SARIF upload), and `container-structure-tests` run in parallel. All three
   must succeed before any release job is triggered.

7. **Bandit pass/fail via JSON post-processing**
   — Bandit is invoked with `-f json` so all findings are captured regardless
   of severity. A post-processing step logs everything (including LOW) but exits
   non-zero only for MEDIUM/HIGH. This avoids the `-ll` flag, which would
   silently suppress LOW findings entirely.

8. **CodeQL exclusion via config file**
   — `dev_environment/` is excluded through `.github/codeql/codeql-config.yml`
   rather than inline `paths-ignore` in the workflow, keeping the exclusion
   auditable alongside other tool configs.

9. **Helm chart version injected at package time**
   — `Chart.yaml` is never modified by CI. The authoritative version is the Git
   tag, injected via `helm package --version` at build time. This mirrors the
   hatch-vcs pattern used for Python packages.

10. **Change detection uses `dorny/paths-filter`**
    — Relevant paths: `middleware/**`, `pyproject.toml`, `docker/**`,
    `scripts/**`, `.github/workflows/**`. PRs that touch only docs, specs, or
    Helm YAML skip all CI jobs without consuming runner minutes.

11. **Required checks always produce a status via step-level `skip` input**
    — GitHub required status checks block PR merges when the job is absent or
    skipped. The solution is a `skip: boolean` input on `reusable-code-quality.yml`
    and `reusable-check.yml`. When `skip: true`, each job in those workflows runs
    but all substantive steps are guarded by `if: ${{ !inputs.skip }}`; only a
    single no-op echo step executes. The job completes with success and GitHub
    records the status. Non-required jobs (`licence-check`, `security-check`,
    `build`) retain their existing `if:` guards and may be skipped entirely.
    `feature-pull-request.yml` always calls both required-check workflows and
    passes `skip: ${{ needs.detect-changes.outputs.code != 'true' }}`.

12. **Upload jobs: no cross-dependency**
    — `push-dockerhub`, `push-ghcr`, and `publish-pypi` have no `needs`
    dependency on each other; they run in parallel. `github-release` uses
    `if: always() && needs.create-release-tag.result == 'success'` so the
    GitHub Release is created regardless of which uploads succeeded. The release
    body is generated dynamically from the individual job results.

13. **Python package distribution names differ from uv workspace names**
    — The uv workspace uses short internal identifiers (`shared`, `api_client`).
    The PyPI distribution names (`fairagro-middleware-shared`,
    `fairagro-middleware-api-client`) are globally namespaced for uniqueness.
    The import path (`middleware.shared`, `middleware.api_client`) is unaffected
    because it is controlled separately by
    `[tool.hatch.build.targets.wheel] packages` in each `pyproject.toml`.

14. **PEP 440 parallel version for Python packages**
    — Docker semver pre-release format (`1.2.3-rc.branch.42`) is not valid
    PEP 440. The build phase computes a parallel `pep440_version` in the format
    `1.2.3a42.branch.name` and injects it via
    `SETUPTOOLS_SCM_PRETEND_VERSION` to override hatch-vcs version discovery,
    so Docker and Python packages share the same numeric baseline.

15. **Registry selection via `release_type` input**
    — The `publish-pypi` job selects `https://upload.pypi.org/legacy/` for
    `release_type == 'final'` and `https://test.pypi.org/legacy/` for
    `release_type == 'feature'`. Separate secrets (`PYPI_TOKEN`,
    `TEST_PYPI_TOKEN`) are used for each registry.

16. **Python packages built once in the build phase, reused in release**
    — `reusable-build.yml` includes a `python-build` job that produces wheels
    and sdists for both publishable packages and uploads them as the artifact
    `python-packages-{version}`. This mirrors the Docker transfer-artifact
    pattern (Decision 5): the artifact that passed the check phase is the one
    that gets published.
