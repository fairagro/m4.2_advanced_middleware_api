# m4.2_advanced_middleware_api

The API component of the advanced middleware that accepts ARCs in RO-Create format and pushes them to the datahub

## Repository Setup

### Required GitHub Secrets

The following secrets must be configured in **Settings → Secrets and variables → Actions**
before the CI/CD pipelines can publish artefacts.

| Secret | Used by | Required | Description |
| ------ | ------- | -------- | ----------- |
| `RENOVATE_TOKEN` | `renovate.yml` | Yes | Fine-grained PAT for the Renovate bot. Needs: Contents (R/W), Pull requests (R/W), Workflows (R/W), Issues (R/W), Metadata (R). |
| `DOCKERHUB_USER` | `reusable-release.yml`, `helm-release.yml` | Optional | DockerHub username. If absent, Docker pushes are skipped. |
| `DOCKERHUB_TOKEN` | `reusable-release.yml`, `helm-release.yml` | Optional | DockerHub access token. If absent, Docker pushes are skipped. |
| `PYPI_TOKEN` | `reusable-release.yml` | Optional | PyPI API token for publishing `fairagro-middleware-shared` and `fairagro-middleware-api-client` on final releases. If absent, PyPI publish is skipped. |
| `TEST_PYPI_TOKEN` | `reusable-release.yml` | Optional | TestPyPI API token for pre-release publishes from feature branches. If absent, TestPyPI publish is skipped. |

> `GITHUB_TOKEN` is provided automatically by GitHub Actions and does not need to be configured.
