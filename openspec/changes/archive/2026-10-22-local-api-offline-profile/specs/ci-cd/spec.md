# Spec Delta

## MODIFIED Requirements

### Requirement: Publish both Python packages

The workflow MUST publish packages for `middleware/api_client`, `middleware/shared`, `middleware/arc_validation`, and
`middleware/api_local_offline` to PyPI whenever a Docker image is successfully pushed.

#### Scenario: A Docker image is pushed

- **GIVEN** a Docker registry upload succeeds
- **WHEN** release publishing runs
- **THEN** all four Python package publication jobs are eligible to run

### Requirement: Use required PyPI distribution names

The API client package MUST be named `fairagro-middleware-api-client`, the shared package MUST be named
`fairagro-middleware-shared`, the ARC export validation package MUST be named `fairagro-middleware-arc-validation`, and
the local offline stand-in package MUST be named `fairagro-middleware-api-local-offline`.

#### Scenario: Build package metadata

- **GIVEN** the four publishable package artifacts
- **WHEN** their distributions are built
- **THEN** they use the required PyPI names

### Requirement: Build complete Python distributions

All four packages MUST include wheels, source distributions, complete README usage instructions, license information,
author and homepage metadata, and all dependencies declared in `pyproject.toml`.

#### Scenario: Inspect package artifacts

- **GIVEN** built distributions for shared, api-client, arc-validation, and api-local-offline
- **WHEN** their contents and metadata are inspected
- **THEN** wheels, sdists, README, license, author/homepage, and declared dependencies are present
