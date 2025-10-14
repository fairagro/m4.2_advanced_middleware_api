# GitHub Workflows

This directory contains GitHub Actions workflows for automated testing, code quality, and deployment.

## Workflows

### 🐍 Python Code Quality (`python-quality.yml`)

**Triggers:** Push to `main`, `develop`, `python` branches and PRs

**Features:**
- **Code Formatting**: Black (88 char line length)
- **Import Sorting**: isort with Black profile
- **Static Analysis**: pylint (minimum score 8.0/10)
- **Type Checking**: mypy (advisory)
- **Security Scanning**: bandit for security vulnerabilities
- **Dependency Check**: safety for known vulnerabilities
- **Unit Tests**: pytest with coverage reporting
- **Codecov Integration**: Automatic coverage upload

**Tools:**
| Tool | Purpose | Status |
|------|---------|--------|
| Black | Code formatting | ✅ Required |
| isort | Import organization | ✅ Required |
| pylint | Code quality & style | ✅ Required (≥8.0) |
| mypy | Type checking | ⚠️ Advisory |
| bandit | Security vulnerabilities | ✅ Required |
| safety | Dependency vulnerabilities | ⚠️ Advisory |
| pytest | Unit tests + coverage | ✅ Required |

### 🐳 Docker Release (`docker-release.yml`)

**Triggers:** Push to `main`, `develop` branches and PRs

**Features:**
- **Version Calculation**: GitVersion semantic versioning
- **Docker Build**: Multi-platform builds with caching
- **Security Scanning**: Trivy vulnerability scanner
- **SBOM Generation**: Software Bill of Materials
- **Container Structure Tests**: Image validation
- **DockerHub Push**: Conditional based on secrets
- **GitHub Releases**: Automated release creation

**New Addition - Container Structure Tests:**
- Validates Docker image structure and security
- Checks file permissions, users, and dependencies
- Runs after successful Docker build
- Tests Python/Flask functionality in container
- Generates JUnit XML reports

## Local Development

### Pre-commit Hooks

Install pre-commit for local quality checks:

```bash
uv add --dev pre-commit
uv run pre-commit install
```

### Manual Quality Checks

```bash
# Install development dependencies
uv sync --extra dev

# Code formatting
uv run black app/ tests/
uv run isort app/ tests/

# Code quality
uv run pylint app/ --fail-under=8.0

# Security
uv run bandit -r app/ -ll

# Type checking
uv run mypy app/ --ignore-missing-imports

# Tests
uv run pytest --cov=app
```

### Container Tests

```bash
# Build image
docker build -t dummy-python-app .

# Download container-structure-test
curl -LO https://storage.googleapis.com/container-structure-test/latest/container-structure-test-linux-amd64
chmod +x container-structure-test-linux-amd64

# Run container tests
./container-structure-test-linux-amd64 test --image dummy-python-app --config tests/container-structure-test.yaml
```

## Status Badges

Add to your README.md:

```markdown
[![Python Code Quality](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/python-quality.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/python-quality.yml)
[![Docker Release](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/docker-release.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/docker-release.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO)
```
