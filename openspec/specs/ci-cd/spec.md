# CI/CD Workflows

## Purpose

GitHub Actions SHALL validate pull requests, build and verify release
artifacts, publish independently to external registries, and report security
findings. The pipelines preserve a deployable `main` branch and provide
traceable Docker, Helm, and Python package releases.

## Requirements

<!-- Pull Request Validation -->

### Requirement: Detect pull-request changes

The pull-request workflow MUST detect files changed on every pull request
targeting `main`.

#### Scenario: A pull request targets main

- **GIVEN** a pull request whose base branch is `main`
- **WHEN** validation starts
- **THEN** the workflow determines whether relevant code files changed

### Requirement: Always report required checks

Every configured required GitHub status check MUST produce a status result for
every pull request targeting `main`; a required check MUST NOT be skipped.

#### Scenario: A docs-only pull request is validated

- **GIVEN** a pull request targeting `main` that changes no code
- **WHEN** validation runs
- **THEN** every required check completes with a status result

### Requirement: Short-circuit non-code pull requests

When a pull request changes only non-code files, required checks MUST complete
successfully without builds, tests, or scans, and non-required jobs MUST be
skipped.

#### Scenario: A pull request changes only documentation, specs, or Helm YAML

- **GIVEN** no relevant code file changed
- **WHEN** pull-request validation runs
- **THEN** required checks succeed through no-op execution and all build and
  scan jobs are skipped

### Requirement: Validate code pull requests

When relevant code files change, every required check MUST run normally and a
failure MUST block the pull-request merge.

#### Scenario: A code-quality check fails for a code change

- **GIVEN** a pull request changes relevant code
- **WHEN** a required validation check fails
- **THEN** GitHub blocks the pull request from merging

### Requirement: Define required checks

The required status checks MUST be named `Container Structure Tests` and
`Code Quality Check`.

#### Scenario: GitHub evaluates required statuses

- **GIVEN** pull-request validation has completed
- **WHEN** branch protection evaluates its checks
- **THEN** it finds statuses named `Container Structure Tests` and `Code Quality Check`

<!-- Code Quality -->

### Requirement: Enforce Ruff formatting

The code-quality workflow MUST verify Ruff formatting and fail if committed code
differs from Ruff's formatted output.

#### Scenario: Formatting drift is committed

- **GIVEN** a changed Python file is not Ruff-formatted
- **WHEN** code quality runs
- **THEN** the formatting check fails

### Requirement: Enforce Ruff and Pylint rules

The code-quality workflow MUST run Ruff linting and Pylint and fail on any
violation.

#### Scenario: A lint rule is violated

- **GIVEN** code contains a Ruff or Pylint violation
- **WHEN** code quality runs
- **THEN** the workflow fails

### Requirement: Enforce MyPy correctness

The code-quality workflow MUST run MyPy and fail on every type error.

#### Scenario: A type error is introduced

- **GIVEN** MyPy identifies a type error
- **WHEN** code quality runs
- **THEN** the workflow fails

### Requirement: Enforce Bandit severity policy

The code-quality workflow MUST log low-severity Bandit findings without
failing and MUST fail for findings above low severity.

#### Scenario: Bandit reports low and medium findings

- **GIVEN** Bandit reports a low-severity finding and a medium-severity finding
- **WHEN** code quality runs
- **THEN** the low finding is logged and the workflow fails because of the
  medium finding

### Requirement: Run the test suite

The code-quality workflow MUST run the full pytest suite and fail when any test
fails.

#### Scenario: A test fails

- **GIVEN** pytest reports a failing test
- **WHEN** code quality runs
- **THEN** the workflow fails

<!-- Versioning and Release Identity -->

### Requirement: Calculate semantic versions

Release workflows MUST calculate a semantic version from the latest relevant
Git tag and a selected `major`, `minor`, or `patch` bump.

#### Scenario: A patch bump is requested

- **GIVEN** the latest relevant tag is available and `patch` is selected
- **WHEN** version calculation runs
- **THEN** it produces the next patch semantic version

### Requirement: Separate Docker and Helm tag namespaces

Docker and Helm versions MUST be calculated independently from `docker-v*` and
`chart-v*` tag namespaces, respectively.

#### Scenario: Docker and Helm have different latest versions

- **GIVEN** the latest Docker and chart tags differ
- **WHEN** each release calculates its version
- **THEN** each uses only its own namespace

### Requirement: Version main releases

A release from `main` MUST use a final `MAJOR.MINOR.PATCH` version.

#### Scenario: Release main

- **GIVEN** a manually dispatched release on `main`
- **WHEN** its version is calculated
- **THEN** it has no pre-release suffix

### Requirement: Version feature releases

A Docker or Helm release from `feature/*` MUST use
`MAJOR.MINOR.PATCH-rc.{branch-label}.{run_number}`, where the branch label
replaces slashes and underscores with hyphens.

#### Scenario: Release a slash-containing feature branch

- **GIVEN** a release from `feature/my_feature/name`
- **WHEN** its version is calculated
- **THEN** its branch label is `my-feature-name` in the release suffix

### Requirement: Create monotonically ordered release tags

Every release MUST create a Git tag with a lexically monotone ordering prefix
across all releases; a `YYYYMMDDhhmmss` prefix is valid.

#### Scenario: Two releases are created sequentially

- **GIVEN** two releases created at different times
- **WHEN** their Git tags are listed lexically
- **THEN** their order is chronological

### Requirement: Format Docker release tags

Docker Git tags MUST use
`{ordering-prefix}-docker-v{major}.{minor}.{patch}[-rc.{branch-label}.{run_number}]`.

#### Scenario: Create a Docker pre-release tag

- **GIVEN** a Docker feature-branch release for version `1.2.3`
- **WHEN** its tag is created
- **THEN** it follows the required Docker pre-release format

### Requirement: Format Helm release tags

Helm Git tags MUST use
`{ordering-prefix}-chart-v{major}.{minor}.{patch}[-rc.{branch-label}.{run_number}]`.

#### Scenario: Create a final Helm tag

- **GIVEN** a final Helm release for version `1.2.3`
- **WHEN** its tag is created
- **THEN** it follows the required final Helm tag format

### Requirement: Name GitHub Releases from tags

The GitHub Release name MUST equal its Git tag with the ordering-prefix and
following hyphen removed.

#### Scenario: Publish a tagged Docker release

- **GIVEN** Git tag `20260421143022-docker-v1.2.3`
- **WHEN** the GitHub Release is created
- **THEN** its name is `docker-v1.2.3`

### Requirement: Support immutable release asset attachment

The release workflow MUST create releases and attach their assets even when
release immutability is enabled.

#### Scenario: Repository releases are immutable

- **GIVEN** release immutability is enabled
- **WHEN** a release with assets is created
- **THEN** the workflow attaches assets before finalizing the release

<!-- Docker Releases -->

### Requirement: Sequence final Docker releases

A manually dispatched final Docker release from `main` MUST run code quality,
build, check, and release jobs in that order.

#### Scenario: Dispatch a final Docker release

- **GIVEN** a manual Docker release on `main`
- **WHEN** the workflow executes
- **THEN** each phase completes successfully before its dependent phase begins

### Requirement: Run pre-release Docker pipelines

A manually dispatched Docker pre-release on any branch MUST run the same
quality, build, check, and release pipeline but MUST NOT create a GitHub
Release entry.

#### Scenario: Dispatch a feature Docker pre-release

- **GIVEN** a manual release from a feature branch
- **WHEN** the release pipeline completes
- **THEN** images are pushed and no GitHub Release entry is created

### Requirement: Publish Docker registries independently

DockerHub and GHCR image uploads MUST run as independent jobs.

#### Scenario: DockerHub upload fails

- **GIVEN** the GHCR and DockerHub upload jobs start
- **WHEN** DockerHub upload fails
- **THEN** the GHCR job is not prevented from completing

### Requirement: Verify images before publishing

The workflow MUST run container structure tests and Trivy scans before an image
is pushed, and MUST NOT push a broken image.

#### Scenario: Container structure testing fails

- **GIVEN** an image fails its container structure tests
- **WHEN** the check phase completes
- **THEN** no registry push occurs

### Requirement: Generate and scan SBOMs

The workflow MUST generate an SBOM for every image, scan both image and SBOM
for vulnerabilities, and upload SARIF results to GitHub Security.

#### Scenario: Build a Docker image

- **GIVEN** an image completes its build
- **WHEN** the check phase runs
- **THEN** an SBOM is generated, both artifacts are scanned, and SARIF is uploaded

<!-- Helm Releases -->

### Requirement: Version Helm charts independently

A Helm release MUST calculate its semantic version independently of Docker.

#### Scenario: Dispatch a Helm release

- **GIVEN** a Helm release is manually dispatched
- **WHEN** its version is calculated
- **THEN** the calculation uses chart tags only

### Requirement: Publish Helm OCI charts

The Helm release workflow MUST package and publish the chart to the DockerHub
OCI registry.

#### Scenario: Release a chart

- **GIVEN** the Helm chart is packaged successfully
- **WHEN** publishing runs
- **THEN** it is uploaded to the DockerHub OCI registry

### Requirement: Apply branch versioning to Helm

Helm releases MUST use final versions on `main` and the defined feature-branch
pre-release version strategy on `feature/*`.

#### Scenario: Release a feature chart

- **GIVEN** a Helm release from a feature branch
- **WHEN** it is tagged and published
- **THEN** it uses the required release-candidate version

### Requirement: Preserve Chart.yaml version

The CI pipeline MUST derive the Helm chart version from Git tags and MUST NOT
modify the `version` field in `Chart.yaml`.

#### Scenario: Package a versioned chart

- **GIVEN** a calculated chart version
- **WHEN** CI packages the chart
- **THEN** it injects the version at package time without changing `Chart.yaml`

<!-- Release Contents -->

### Requirement: Provide image usage instructions

Every GitHub Release body MUST include exact `docker pull` commands and
registry links for published images.

#### Scenario: Publish a Docker GitHub Release

- **GIVEN** a final Docker release is created
- **WHEN** its body is generated
- **THEN** it contains exact pull commands and registry links

### Requirement: Provide image metadata

Every GitHub Release body MUST include a technical metadata table with image
architecture and its corresponding SHA256 digest.

#### Scenario: Publish a Docker GitHub Release (2)

- **GIVEN** image metadata is available
- **WHEN** the release body is generated
- **THEN** it identifies the architecture and image digest

### Requirement: Attach SPDX SBOMs

Every GitHub Release MUST include its corresponding SPDX SBOM as a release
asset.

#### Scenario: Finalize a release

- **GIVEN** the image SBOM was generated
- **WHEN** the GitHub Release is published
- **THEN** the SPDX SBOM is attached

### Requirement: Document local Docker builds

Every GitHub Release body MUST document how to build the image locally from
the specific release tag.

#### Scenario: A user reads a release page

- **GIVEN** a published GitHub Release
- **WHEN** a user needs a fallback build
- **THEN** the body explains how to build from that release tag

<!-- Security Scanning -->

### Requirement: Run scheduled and branch CodeQL analysis

CodeQL MUST analyze Python and GitHub Actions on every push to `feature/*` and
on a weekly schedule.

#### Scenario: Push to a feature branch

- **GIVEN** commits are pushed to `feature/example`
- **WHEN** the CodeQL workflow triggers
- **THEN** it analyzes Python and GitHub Actions

### Requirement: Exclude development environment from CodeQL

CodeQL analysis MUST exclude `dev_environment/`.

#### Scenario: CodeQL selects analysis paths

- **GIVEN** CodeQL configuration is loaded
- **WHEN** paths are selected
- **THEN** `dev_environment/` is excluded

### Requirement: Publish CodeQL findings

CodeQL MUST upload its results to GitHub Security.

#### Scenario: CodeQL analysis completes

- **GIVEN** CodeQL produces results
- **WHEN** analysis finishes
- **THEN** the results are uploaded to GitHub Security

<!-- Python Package Publishing -->

### Requirement: Publish both Python packages

The workflow MUST publish packages for `middleware/api_client` and
`middleware/shared` to PyPI whenever a Docker image is successfully pushed.

#### Scenario: A Docker image is pushed

- **GIVEN** a Docker registry upload succeeds
- **WHEN** release publishing runs
- **THEN** both Python package publication jobs are eligible to run

### Requirement: Publish packages for all releases

Both final `main` releases and feature-branch pre-releases MUST publish to
PyPI.

#### Scenario: Publish a feature release

- **GIVEN** a feature-branch release reaches publishing
- **WHEN** PyPI credentials are available
- **THEN** its packages are published to PyPI

### Requirement: Gate package publishing on security checks

Package publishing MUST begin only after `reusable-check.yml` security scans
have passed.

#### Scenario: Security checks fail

- **GIVEN** a reusable security check fails
- **WHEN** the release reaches publishing
- **THEN** no package is published

### Requirement: Use required PyPI distribution names

The API client package MUST be named `fairagro-middleware-api-client`, and the
shared package MUST be named `fairagro-middleware-shared`.

#### Scenario: Build package metadata

- **GIVEN** the two publishable package artifacts
- **WHEN** their distributions are built
- **THEN** they use the required PyPI names

### Requirement: Build complete Python distributions

Both packages MUST include wheels, source distributions, complete README usage
instructions, license information, author and homepage metadata, and all
dependencies declared in `pyproject.toml`.

#### Scenario: Inspect package artifacts

- **GIVEN** package distributions were built
- **WHEN** their metadata and contents are inspected
- **THEN** each contains the required distributions, documentation, licensing,
  metadata, and dependencies

### Requirement: Align package numeric versions

Python packages MUST use the same numeric semantic version as the Docker image:
`MAJOR.MINOR.PATCH` on `main`, and `MAJOR.MINOR.PATCH.dev{RUN_NUMBER}` for
feature pre-releases.

#### Scenario: Build a feature package release

- **GIVEN** Docker version `1.2.3-rc.example.42`
- **WHEN** Python packages are built
- **THEN** they use PEP 440 version `1.2.3.dev42`

### Requirement: Document released Python packages

When a GitHub Release is created, it MUST list the packages as artifacts,
provide exact-version `pip install` commands, and include fallback local
installation instructions.

#### Scenario: Create a final GitHub Release

- **GIVEN** final Python packages were published
- **WHEN** the GitHub Release body is generated
- **THEN** it lists the packages, exact install commands, and local-install fallback

<!-- Independent Upload Handling -->

### Requirement: Isolate external uploads

Each DockerHub, GHCR, and PyPI external upload MUST be a standalone job
independent of other upload jobs.

#### Scenario: One external publisher is unavailable

- **GIVEN** release upload jobs run in parallel
- **WHEN** one uploader fails
- **THEN** the other upload jobs remain able to complete

### Requirement: Tolerate upload failures

An external upload failure MUST NOT make the release unsuccessful.

#### Scenario: GHCR upload fails after the release is built

- **GIVEN** build and verification succeeded
- **WHEN** the GHCR upload fails
- **THEN** the release workflow continues as successful

### Requirement: Warn about incomplete release uploads

When a GitHub Release is created, its body MUST document successful artifacts
and MUST include a warning for every failed external upload, including missing
credentials treated as an upload failure.

#### Scenario: DockerHub credentials are absent

- **GIVEN** DockerHub credentials are unavailable during a final release
- **WHEN** build and verification complete
- **THEN** the DockerHub push is skipped, the completed build and tests remain
  valid, and the GitHub Release body warns that DockerHub upload did not occur
  while documenting only successfully uploaded artifacts

#### Scenario: PyPI credentials are absent

- **GIVEN** PyPI credentials are unavailable
- **WHEN** the release reaches package publication
- **THEN** package publishing is skipped and the GitHub Release can still be created

### Requirement: Fail before artifacts on version calculation errors

If a version cannot be calculated from Git history, the pipeline MUST fail
before building and MUST produce no artifact.

#### Scenario: No valid version baseline exists

- **GIVEN** the version calculator cannot determine a version from Git history
- **WHEN** a release starts
- **THEN** it fails before any build or artifact production

### Requirement: Tag feature releases without GitHub Releases

A feature-branch release MUST create its Git tag for version tracking even
though it creates no GitHub Release entry.

#### Scenario: Complete a feature release

- **GIVEN** a feature-branch release succeeds
- **WHEN** its publication phase completes
- **THEN** its version tag exists and no GitHub Release entry exists
