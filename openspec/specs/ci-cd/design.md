# CI/CD Workflows Design

## Workflow Topology

```text
PR → main
  feature-pull-request.yml
    ├─ reusable-code-quality.yml
    ├─ reusable-build.yml (push=false)
    └─ reusable-check.yml

workflow_dispatch pre-release (any branch)
  pre-release.yml
    ├─ reusable-code-quality.yml
    ├─ reusable-build.yml (push=true)
    ├─ reusable-check.yml
    └─ reusable-release.yml (no GitHub Release)

workflow_dispatch final release (main)
  release.yml
    ├─ reusable-code-quality.yml
    ├─ reusable-build.yml (push=true)
    ├─ reusable-check.yml
    └─ reusable-release.yml (GitHub Release)

workflow_dispatch Helm release
  helm-release.yml → package and publish chart

push to feature/* or weekly schedule
  codeql.yml → Python and GitHub Actions analysis
```

Reusable workflows separate responsibilities:

- `reusable-code-quality.yml`: Ruff, Pylint, MyPy, Bandit, and pytest.
- `reusable-build.yml`: version calculation, Docker and Python package builds,
  and SBOM generation.

- `reusable-check.yml`: licence, vulnerability, and container structure checks.
- `reusable-release.yml`: independent external upload jobs, Git tags, and
  GitHub Release creation.

## Design Decisions

### Version calculation and ordering

A small Bash implementation finds the newest semantic tag in the required
namespace and applies the selected bump. This avoids a .NET GitVersion
dependency. A fixed-width `YYYYMMDDhhmmss` prefix makes lexical and
chronological tag ordering equivalent while the human-facing release name
omits that prefix.

Feature releases still create Git tags even without GitHub Release entries.
The `rc.{branch-label}.{run-number}` suffix groups a branch's releases and
orders its builds. Python uses the corresponding PEP 440
`MAJOR.MINOR.PATCH.devRUN_NUMBER` version, injected at build time to override
hatch-vcs discovery.

### Immutable GitHub Releases

To attach assets when release immutability is enabled, the workflow creates a
draft release, uploads assets, then publishes it with a GitHub API patch. The
same draft-to-publish approach applies to Docker and Helm releases.

### Artifact transfer and checks

The build workflow saves the built image, SBOM, and Python distributions as
Actions artifacts. Check and release workflows consume those artifacts instead
of rebuilding, ensuring the verified image and packages are precisely the ones
released.

Licence checks, security checks (Trivy plus SARIF upload), and container
structure tests form independent parallel check groups. All must pass before
release jobs start. Bandit emits JSON, logs low findings, and fails only when
post-processing identifies medium or high severity. CodeQL path exclusions are
kept in `.github/codeql/codeql-config.yml`.

### Pull-request change detection

`dorny/paths-filter` detects relevant changes in `middleware/**`,
`pyproject.toml`, `docker/**`, `scripts/**`, and `.github/workflows/**`.
Documentation, specifications, and Helm-only changes do not consume build or
scan runner time.

Required checks cannot be job-skipped because that leaves branch protection
without a status. `reusable-code-quality.yml` and `reusable-check.yml` accept
a boolean `skip` input; they still run a successful no-op step when it is true,
while every substantive step is guarded. Non-required build, licence, and
security jobs retain normal job-level guards.

### Independent publishing and release reporting

DockerHub, GHCR, and PyPI publishing have no dependencies on one another and
run in parallel after successful checks. A release creation job runs whenever
tag creation succeeded, regardless of each publisher's outcome. It constructs
the body from individual job results, documents only successful artifacts, and
warns for failed or credential-skipped uploads.

The uv workspace's internal package identifiers remain `shared` and
`api_client`; package metadata publishes globally distinct PyPI distribution
names. Wheel and source distributions are built once during the build phase
and reused by publication jobs.

### Helm packaging

Chart version is authoritative in the Git tag. CI injects it with
`helm package --version` and never modifies `Chart.yaml`, matching the
tag-derived version approach used by Python package builds.
