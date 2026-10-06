# Spec Delta

## MODIFIED Requirements

### Requirement: Detect pull-request changes

The pull-request workflow MUST detect files changed on every pull request targeting `main`. It MUST classify changes
into at least two independent sets: relevant **code** files and relevant **Helm chart** files.

#### Scenario: A pull request targets main

- **GIVEN** a pull request whose base branch is `main`
- **WHEN** validation starts
- **THEN** the workflow determines whether relevant code files changed and whether relevant Helm chart files changed

### Requirement: Short-circuit non-code pull requests

When a pull request changes only non-code files, required checks MUST complete successfully without builds, tests, or
scans, and non-required Docker build and scan jobs MUST be skipped. Helm chart files are not code for this requirement:
their presence MUST NOT by itself start Docker build or scan jobs.

#### Scenario: A pull request changes only documentation, specs, or Helm YAML

- **GIVEN** no relevant code file changed
- **WHEN** pull-request validation runs
- **THEN** required checks succeed through no-op execution and all Docker build and scan jobs are skipped

#### Scenario: A pull request changes only documentation or specs

- **GIVEN** no relevant code file and no relevant Helm chart file changed
- **WHEN** pull-request validation runs
- **THEN** required checks succeed through no-op execution and Helm chart lint is skipped

## ADDED Requirements

### Requirement: Validate Helm chart pull requests

When relevant Helm chart files change, the pull-request workflow MUST lint the product Helm chart and MUST fail the Helm
lint job when lint (or the optional default-values template smoke) fails. Chart-only changes MUST NOT start Docker build
or scan jobs.

#### Scenario: A Helm-only pull request is linted

- **GIVEN** a pull request targeting `main` that changes Helm chart files and no relevant code files
- **WHEN** pull-request validation runs
- **THEN** Helm chart lint runs against the product chart and Docker build and scan jobs do not start

#### Scenario: Helm lint fails for a chart change

- **GIVEN** a pull request that changes Helm chart files
- **WHEN** Helm chart lint fails
- **THEN** the Helm lint job fails

#### Scenario: A code-only pull request skips Helm lint

- **GIVEN** a pull request targeting `main` that changes relevant code files and no Helm chart files
- **WHEN** pull-request validation runs
- **THEN** Helm chart lint completes without linting the chart
