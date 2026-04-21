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

On workflow_dispatch (Release, main only):
    release.yml
        ├─→ reusable-code-quality.yml
        ├─→ reusable-build.yml        (push=true)
        ├─→ reusable-check.yml
        └─→ reusable-release.yml      (creates GitHub Release)

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
| `reusable-build.yml` | Version calc, Docker build, SBOM generation |
| `reusable-check.yml` | Licence scan, Trivy vuln scan, container structure tests |
| `reusable-release.yml` | Docker push (DockerHub + GHCR), Git tag, GitHub Release |

## Key Decisions

1. **Bash-based version calculation**
   — Versions are calculated with a short bash script: find the latest
   semver Git tag in the appropriate namespace (`v*` for Docker, `chart-v*`
   for Helm), parse it, apply the bump, and produce the new version.
   GitVersion (a .NET tool) was considered but rejected because it introduces
   a heavyweight external dependency for a task that a few lines of bash
   handle transparently and auditably inside the workflow file itself.

2. **Timestamp as ordering prefix for Git tags**
   — The GitHub releases page sorts releases by tag name. Sorting by semver
   alone is unreliable when patch and minor releases interleave. The spec
   requires a lexically monotone ordering prefix; a `YYYYMMDDhhmmss` timestamp
   generated via `date +%Y%m%d%H%M%S` at job start satisfies this because its
   fixed length (14 characters) ensures lexical sort equals chronological sort.
   The ordering prefix is stripped from the human-readable GitHub Release name,
   so releases display as `docker-v1.2.3` or `chart-v1.2.3-rc.my-feature.42`.

3. **Draft → Publish pattern for immutable releases**
   — GitHub repository releases have immutability enabled (`Enable release
   immutability` setting). Once published, a release cannot be modified —
   including adding assets. To support attaching files, releases are always
   created as `draft: true` first (allowing asset uploads), then published
   by a separate `gh api PATCH draft=false` call. This applies to both
   Docker releases (`reusable-release.yml`) and Helm chart releases
   (`helm-release.yml`).

4. **Feature branch releases always create a Git tag**
   — A Git tag is created on every release run, including feature branch
   pre-releases that produce no GitHub Release entry. This ensures the version
   calculator always finds a valid baseline when calculating the next version,
   regardless of whether the previous run produced a published release.
   The suffix order `rc.{branch-label}.{run_number}` is chosen so that
   pre-release versions sort first by branch (grouping all builds from the
   same feature together) and then by run number within that branch.

5. **Build phase: Docker image as the transfer artifact**
   — `reusable-build.yml` builds the Docker image, saves it as a gzip
   artifact (`docker-image-{component}-{version}`), and generates an SBOM
   (`sbom-{component}-{version}`). Downstream jobs (`reusable-check.yml`,
   `reusable-release.yml`) download these artifacts rather than rebuilding.
   This guarantees that the checked and released image are byte-for-byte
   identical to the built image.

6. **Check phase: licence, security, and container structure**
   — `reusable-check.yml` runs three independent job groups:
   `licence-check` (Trivy licence scanner), `security-check` (Trivy vuln
   scan on image + SBOM, SARIF upload to GitHub Security), and
   `container-structure-tests`. All three must pass before a release job runs.

7. **Bandit uses project `.bandit` config**
   — Bandit is invoked as `bandit -r middleware/ -c .bandit -ll`, delegating
   all severity and exclusion configuration to the `.bandit` file checked into
   the repository. This keeps CI and local development behaviour consistent.

8. **CodeQL config excludes `dev_environment/`**
   — A `.github/codeql/codeql-config.yml` file instructs CodeQL to skip the
   `dev_environment/` directory, which contains Docker Compose configuration
   and secrets that are not part of the application code.

9. **Helm chart version: Git tag is authoritative**
   — `Chart.yaml` is never modified by the CI pipeline. The authoritative
   chart version is the Git tag; CI passes it to `helm package --version` at
   package time. This mirrors the hatch-vcs pattern used for Python packages.

10. **Change detection on pull requests**
    — `feature-pull-request.yml` runs a `detect-changes` job first using
    `dorny/paths-filter`. All downstream jobs (`code-quality`, `build`,
    `check`) are skipped unless at least one of the following paths changed:
    `middleware/**`, `pyproject.toml`, `docker/**`, `scripts/**`,
    `.github/workflows/**`. PRs that only touch documentation, specs, or
    Helm chart YAML finish instantly without consuming CI minutes.
