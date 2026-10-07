# Spec Delta

## MODIFIED Requirements

### Requirement: Publish both Python packages

The workflow MUST publish packages for `middleware/api_client`, `middleware/shared`, and `middleware/arc_validation` to
PyPI whenever a Docker image is successfully pushed.

#### Scenario: A Docker image is pushed

- **GIVEN** a Docker registry upload succeeds
- **WHEN** release publishing runs
- **THEN** all three Python package publication jobs are eligible to run

### Requirement: Use required PyPI distribution names

The API client package MUST be named `fairagro-middleware-api-client`, the shared package MUST be named
`fairagro-middleware-shared`, and the ARC export validation package MUST be named `fairagro-middleware-arc-validation`.

#### Scenario: Build package metadata

- **GIVEN** the three publishable package artifacts
- **WHEN** their distributions are built
- **THEN** they use the required PyPI names

### Requirement: Build complete Python distributions

All three packages MUST include wheels, source distributions, complete README usage instructions, license information,
author and homepage metadata, and all dependencies declared in `pyproject.toml`.

#### Scenario: Inspect package artifacts

- **GIVEN** built distributions for shared, api-client, and arc-validation
- **WHEN** their contents and metadata are inspected
- **THEN** wheels, sdists, README, license, author/homepage, and declared dependencies are present
