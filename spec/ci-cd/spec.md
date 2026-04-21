# CI/CD Workflows

**Scope:** Automated pipelines that validate pull requests, build and publish
Docker images and Helm charts, and scan for security vulnerabilities. All
pipelines run on GitHub Actions.

## Requirements

<!-- Pull Request Validation -->
- [ ] On every pull request targeting `main`, detect which files changed and
      skip all CI jobs when only non-code files (docs, specs, Helm chart YAML)
      were modified.
- [ ] On every pull request targeting `main`, run code quality checks, build
      the Docker image, and execute all check jobs.
- [ ] On every pull request, verify code quality (formatting, linting, type
      checking, security, tests) and fail the PR if any check fails.
- [ ] On every pull request, build the Docker image, generate an SBOM, run
      licence checks, security scans, and container structure tests; do not
      push the image to any registry.

<!-- Code Quality -->
- [ ] Enforce consistent code formatting with Ruff; fail when committed code
      differs from the formatted output.
- [ ] Enforce linting rules with Ruff and Pylint; fail on any violation.
- [ ] Enforce static type correctness with MyPy; fail on any type error.
- [ ] Scan for security vulnerabilities with Bandit; log low-severity findings
      without failing; fail on any finding with severity higher than low.
- [ ] Run the full test suite with pytest; fail when any test fails.

<!-- Version Calculation -->
- [ ] Calculate semantic versions from the latest Git tag and the chosen bump
      type (`major` / `minor` / `patch`).
- [ ] Docker and Helm chart versions are tracked independently via separate tag
      namespaces (`docker-v*` and `chart-v*`).
- [ ] On `main`, produce a final `MAJOR.MINOR.PATCH` version.
- [ ] On a `feature/*` branch, produce a pre-release version with the format
      `MAJOR.MINOR.PATCH-rc.{branch-label}.{run_number}`, where `{branch-label}`
      is the feature name with the `feature/` prefix stripped.

<!-- Git Tag and Release Naming -->
- [ ] Every release creates a Git tag with an ordering prefix that is
      lexically monotone increasing across all releases, so the GitHub releases
      page sorts tags in chronological order. A `YYYYMMDDhhmmss` timestamp is
      one valid choice for such a prefix.
- [ ] Docker Git tag format:
      `{ordering-prefix}-docker-v{major}.{minor}.{patch}[-rc.{branch-label}.{run_number}]`
      Example: `20260421143022-docker-v1.2.3` or `20260421143022-docker-v1.2.3-rc.my-feature.42`
- [ ] Helm chart Git tag format:
      `{ordering-prefix}-chart-v{major}.{minor}.{patch}[-rc.{branch-label}.{run_number}]`
      Example: `20260421143022-chart-v1.2.3` or `20260421143022-chart-v1.2.3-rc.my-feature.42`
- [ ] The GitHub Release name equals the Git tag name with the
      `{ordering-prefix}-` prefix stripped.
      Examples: `docker-v1.2.3`, `chart-v1.2.3`
- [ ] GitHub Releases must be fully creatable (including asset attachment) even
      when release immutability is enabled on the repository.

<!-- Docker Release -->
- [ ] On a manually triggered final release (from `main`), run code quality,
      build, check, and release jobs in sequence.
- [ ] On a manually triggered pre-release (any branch), run the same pipeline
      but push images without creating a GitHub Release entry.
- [ ] Push Docker images to DockerHub and GitHub Container Registry (GHCR).
- [ ] Run container structure tests and Trivy scans before pushing; do not push
      a broken image.
- [ ] Generate an SBOM for every built image.
- [ ] Scan both the image and the SBOM for vulnerabilities; upload SARIF
      results to GitHub Security.

<!-- Helm Chart Release -->
- [ ] On a manually triggered Helm release, calculate a semantic version for
      the chart independently of the Docker image version.
- [ ] Package and publish the Helm chart to DockerHub OCI registry.
- [ ] Apply the same `main` / `feature/*` version strategy as Docker releases.
- [ ] The Helm chart version is derived from Git tags alone; the `version`
      field in `Chart.yaml` is not modified by the CI pipeline.

<!-- Release Body -->
- [ ] Every GitHub Release body must contain concrete usage instructions:
      the exact `helm install` and `docker run` commands with the published
      image URLs and chart version for that release.
- [ ] If Docker image push to DockerHub or GHCR was skipped or failed, the
      release body must document the fallback: how to build the image locally
      and how to install the Helm chart directly from the GitHub release asset.

<!-- Security Scanning -->
- [ ] Run CodeQL static analysis for Python and GitHub Actions on every push to
      a `feature/*` branch and on a weekly schedule.
- [ ] Exclude `dev_environment/` from CodeQL analysis.
- [ ] Upload CodeQL results to GitHub Security.

## Edge Cases

Docker build or container tests fail → image is not pushed to any registry.

Version cannot be calculated from Git history → pipeline fails before build;
no artifact is produced.

Feature branch release → pre-release image/chart published; no GitHub Release
entry created; Git tag is still created for version tracking.

DockerHub credentials absent → push step is skipped; build and tests still run.
