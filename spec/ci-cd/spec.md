# CI/CD Workflows

**Scope:** Automated pipelines that validate pull requests, build and publish
Docker images and Helm charts, and scan for security vulnerabilities. All
pipelines run on GitHub Actions.

## Requirements

<!-- Pull Request Validation -->
- [ ] On every pull request targeting `main`, detect which files changed.
- [ ] On every pull request targeting `main`, every job that is configured as a
      required GitHub status check must always produce a status result — it must
      never be skipped.
- [ ] When only non-code files (docs, specs, Helm chart YAML) were modified, all
      required checks must complete immediately with a success status, without
      performing any actual work (no builds, no test runs, no scans). Jobs that
      are not required are skipped.
- [ ] When code files were modified, all required checks run normally; failures
      block the PR merge.
- [ ] Required Checks are: "Container Structure Tests" and "Code Quality Check"

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
      is the sanitized feature name (e.g., slashes and underscores replaced by hyphens).

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
- [ ] Push Docker images to DockerHub and GitHub Container Registry (GHCR) in independent jobs.
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
      the exact `docker pull` commands and registry links for the published
      image.
- [ ] Every GitHub Release body must contain a technical metadata table
      providing the image architecture (e.g., `linux/amd64`) and the
      corresponding image digest (SHA256).
- [ ] Every GitHub Release must have the corresponding SBOM (Software Bill of
      Materials) in SPDX format attached as a release asset.
- [ ] The release body documents the fallback: how to build the image locally
      from the specific release tag.

<!-- Security Scanning -->
- [ ] Run CodeQL static analysis for Python and GitHub Actions on every push to
      a `feature/*` branch and on a weekly schedule.
- [ ] Exclude `dev_environment/` from CodeQL analysis.
- [ ] Upload CodeQL results to GitHub Security.

<!-- Python Package Publishing -->

- [ ] Publish Python packages to PyPI for `middleware/api_client` and `middleware/shared` components.
- [ ] PyPI packages must be published whenever a Docker image is successfully pushed to a registry.
- [ ] Both final releases from `main` and feature branch pre-releases must publish packages to **PyPI** (<https://pypi.org>).
- [ ] Packages must be published only after the `reusable-check.yml` security scans have passed.
- [ ] Publish the `middleware/api_client` component under the name `fairagro-middleware-api-client`.
- [ ] Publish the `middleware/shared` component under the name `fairagro-middleware-shared`.
- [ ] Both packages must include wheels and source distributions.
- [ ] Each package must include complete `README.md` with usage instructions.
- [ ] Each package must include license information.
- [ ] Each package must include project metadata including author and homepage.
- [ ] Each package must include required dependencies from `pyproject.toml`.
- [ ] PyPI packages must use the exact same semantic version as the Docker image.
- [ ] Final release from `main`: `MAJOR.MINOR.PATCH`.
- [ ] Feature branch pre-release: `MAJOR.MINOR.PATCH.dev{RUN_NUMBER}` (PEP 440 compliant format using global run number for uniqueness).
- [ ] If a GitHub release is created, the packages must be added to the artifact list.
- [ ] If a github release is created, include `pip install` commands for each package with exact version information.
- [ ] If a GitHub release is created, provide fallback instructions for local installation from source.

<!-- General considerations -->

- [ ] Each upload to an external service (DockerHub, GHCR, PyPI) must be modelled as a standalone job, independent from other upload jobs.
- [ ] If an upload job fails, the release is still considered successful.
- [ ] If a GitHub release is created, the body must document the usage of successfully uploaded artifacts, as specified above.
- [ ] If an upload job fails and a GitHub release is created, issue a corresponding warning message in the GitHub release.
- [ ] If the credentials for an external service are missing, treat this like an upload failure. Adapt the GitHub release body warning accordingly.

### Edge Cases

Docker build or container tests fail → image is not pushed to any registry.

Version cannot be calculated from Git history → pipeline fails before build;
no artifact is produced.

Only non-code files changed in a PR → required status checks complete immediately
with success; Docker build and scan jobs are skipped entirely.

Feature branch release → pre-release image/chart published; no GitHub Release
entry created; Git tag is still created for version tracking.

DockerHub credentials absent → push step is skipped; build and tests still run.

PyPI credentials absent → skip publishing but continue with GitHub Release.
