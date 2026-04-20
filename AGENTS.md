# AGENTS.md - Instructions for AI Assistants

This file contains critical context about the FAIRagro Advanced Middleware API project for AI assistants (GitHub Copilot, Claude, etc.).

## 📋 Tech Stack

| Component | Version | Details |
| --------- | ------- | ------- |
| Python | 3.12.12 | Primary language |
| FastAPI | Latest | REST API framework |
| Pydantic | V2 | Configuration validation |
| Celery | Latest | Async task queue (GitLab sync worker) |
| CouchDB | Latest | Fast document store (ARC + harvest metadata) |
| RabbitMQ | Latest | Message broker for Celery |
| Docker | Latest | Containerization |
| Git LFS | 3.3.0+ | Large file storage |
| uv | Latest | Python package manager |

## 📁 Project Structure

```text
.agents/
└── skills/                # Agent Skills (agentskills.io standard)
    ├── arctrl/            # arctrl Python library reference
    ├── config-wrapper/    # ConfigWrapper / ConfigBase pattern
    └── create-specifica-feature/  # How to create a new Specifica feature

.github/
└── agents/
    └── spec-to-code.agent.md     # Spec-to-code custom agent

docs/
└── ai_workflow.md         # AI agent workflow documentation

spec/                      # Project-level architecture & design
└── principles.md          # Foundation contract, project values

middleware/
├── shared/                 # Shared utilities & configuration
│   └── config/
│       └── config_wrapper.py    # ConfigWrapper with primitive types (24 tests, 86.53% coverage)
├── api/                    # FastAPI REST API
│   ├── spec/              # Component-level architecture & design
│   │   ├── arc-manager/        # Two-phase ARC ingest: CouchDB + async GitLab sync
│   │   ├── arc-store/          # ArcStore interface + GitRepo implementation
│   │   ├── document-store/     # CouchDB persistence layer
│   │   └── harvest-management/ # Harvest run lifecycle and ownership
│   └── src/middleware/api/
├── api_client/            # Client library for API
│   └── config.py          # Optional certificate support (26 tests)

scripts/
├── load-env.sh           # Environment setup (MAIN ENTRY POINT for hooks)
├── setup-git-lfs.sh      # Git LFS installation
└── git-hooks/            # Version-controlled hooks
    ├── pre-push          # Combined: Git LFS + pre-commit
    ├── post-checkout
    ├── post-commit
    └── post-merge

dev_environment/
├── start.sh              # Start Docker Compose with sops
├── compose.yaml          # Docker services definition
└── config.yaml           # Development configuration
```

## 🔧 Important Commands

### Always use `uv` for Python

```bash
# Tests
uv run pytest middleware/shared/tests/unit/ -v
uv run pytest middleware/api_client/tests/unit/ -v

# Quality checks
uv run ruff check .
uv run mypy middleware/

# Ruff parity checks (local + pre-commit + CI)
uv run ruff format --check --diff middleware/
uv run ruff check middleware/

# Install all dependecies
uv sync --dev --all-packages
```

## 📝 Key Implementation Details

### ConfigWrapper (`middleware/shared/config/config_wrapper.py`)

**Purpose**: Wrap YAML configs with environment variable overrides and type conversion

**Features**:

- Supports dict, list, and primitive types
- Automatic type parsing from environment variables
- Fallback chain: bool → int → float → string
- Docker secret support

**Example**:

```python
from middleware.shared.config.config_wrapper import ConfigWrapper

config = ConfigWrapper(yaml_data, environment_vars={})
port = config["server"]["port"]  # int: 8080
debug = config["app"]["debug"]   # bool: True
```

**Test Coverage**: 24/24 tests passing, 86.53% coverage

### ApiClient (`middleware/api_client/src/middleware/api_client/`)

**Purpose**: Type-safe HTTP client for Middleware API

**Features**:

- Optional mTLS authentication (certificates can be None)
- SSL/TLS verification support
- Async/await with context manager support
- Request/response logging

**Key Change**: Client certificates are now OPTIONAL

```python
# Valid configurations:
config1 = Config(api_url="http://api.local")  # No certs
config2 = Config(
    api_url="https://api.example.com",
    client_cert_path=Path("client.crt"),
    client_key_path=Path("client.key")
)
```

**Test Coverage**: 26/26 tests passing

### Git LFS Integration

**Setup Process**:

1. `scripts/load-env.sh` is sourced during development
2. This script calls `scripts/setup-git-lfs.sh`
3. Git LFS hooks are installed from `scripts/git-hooks/`
4. Hooks are version-controlled, not just in `.git/hooks/`

**Files Tracked by LFS**: `*.sql` (configured in `.gitattributes`)

## 🐳 Docker Compose Services

```yaml
services:
  postgres:           # PostgreSQL database
  db-init:            # Database initialization with Edaphobase dump
  middleware-api:     # FastAPI REST API
  celery-worker:      # Celery worker process
  couchdb:            # CouchDB for RDI storage
```

**Configuration**: `dev_environment/config.yaml`

- `db_name`: edaphobase
- `api_client.api_url`: <http://middleware-api:8000>
- `api_client.client_cert_path`: null (optional)
- `api_client.client_key_path`: null (optional)

## 🧪 Testing Strategy

### Test Locations

- `middleware/shared/tests/unit/` - ConfigWrapper tests
- `middleware/api_client/tests/unit/` - ApiClient tests
- `middleware/api/tests/` - API endpoint tests

### Running Tests with uv

```bash
# Run all tests
uv run pytest

# Run specific module
uv run pytest middleware/shared/tests/unit/ -v

# Run with coverage
uv run pytest --cov=middleware/shared middleware/shared/tests/

# Run specific test
uv run pytest middleware/shared/tests/unit/test_config_wrapper.py::test_parse_primitive_value_int -v
```

## 🔐 Security Notes

- Client certificates are optional but recommended for production
- Empty environment variables are converted to `None`, not empty strings
- SSL verification is enabled by default
- CA certificates can be optionally provided

## ✨ Code Quality Standards

Agents are expected to maintain high code quality by addressing issues reported by the project's configured tools: **Ruff, Pylance, MyPy, Pylint, and Bandit**.

- **Automatic Fixes**: Actively check for and fix code smells, warnings, and notices.
- **Real Fixes vs. Suppression**: Issues must be resolved with actual code changes. Using comments to suppress warnings (e.g., `# noqa`, `# type: ignore`, `# pylint: disable`) is an **option of last resort**.
- **When to Suppress**: Only suppress if a fix is technically impossible or would result in unnecessarily complex or unreadable code.
- **Comprehensive Coverage**: Fix all reported issues, including low-severity notices and warnings, not just critical errors.

### Ruff Execution Consistency

- Keep Ruff behavior identical in VS Code, pre-commit, and GitHub Actions by using the same scope (`middleware/`) and the same root config (`pyproject.toml`).
- If `uv run ruff ...` fails before Ruff starts and shows `packaging.version.InvalidVersion` from `hatch-vcs`, the failure is in package version resolution, not Ruff itself.
- In that case, verify `tool.hatch.version.raw-options` in `middleware/*/pyproject.toml` can parse repository tags used by CI/release workflows.

## 📚 File Modifications Pattern

When editing files:

1. **Always check current state** - Use `read_file` to see current content
2. **Use `replace_string_in_file`** - Include 3-5 lines of context before/after
3. **Never modify `.git/` directly** - Use scripts instead
4. **Test after changes** - Always run relevant tests with `uv run pytest`

## 🏗️ Architecture & Design

**Read [`spec/principles.md`](spec/principles.md) first.** It defines module
dependency rules, configuration constraints, typing rules, and code quality
requirements. Do not restate what is there.

Before generating or modifying code, read the relevant spec folders:

**Project-level** (`spec/`) — cross-cutting concerns:

- **[`spec/principles.md`](spec/principles.md)** — Authoritative project principles (start here).

**API component** (`middleware/api/spec/`) — api internals:

- **[`middleware/api/spec/arc-upload/`](middleware/api/spec/arc-upload/)** — HTTP contract for `POST /v3/arcs`: standalone ARC submission (rdi from request body).
- **[`middleware/api/spec/harvest-arc-upload/`](middleware/api/spec/harvest-arc-upload/)** — HTTP contract for `POST /v3/harvests/{harvest_id}/arcs`: ARC submission within a harvest run (rdi resolved from harvest).
- **[`middleware/api/spec/arc-manager/`](middleware/api/spec/arc-manager/)** — `ArcManager.create_or_update_arc` business logic: CouchDB storage, idempotency, Celery dispatch, harvest statistics. Shared by both upload endpoints and accessible from the worker context.
- **[`middleware/api/spec/arc-store/`](middleware/api/spec/arc-store/)** — `ArcStore` Git-backend interface: `GitRepo` (primary) and `GitlabApi` (deprecated), error classification, and credential injection.
- **[`middleware/api/spec/document-store/`](middleware/api/spec/document-store/)** — CouchDB persistence layer, race-condition-safe initialization, and content-hash idempotency.
- **[`middleware/api/spec/harvest-management/`](middleware/api/spec/harvest-management/)** — Harvest run lifecycle, ownership validation, and progress tracking.

For the AI agent workflow documentation, see [`docs/ai_workflow.md`](docs/ai_workflow.md).

### Spec-to-Code Mapping

This table maps each spec folder to the primary source file(s) it describes.
The `spec-to-code` agent uses this table in Step 3 to locate affected code.

| Spec folder | Primary source file(s) |
| ----------- | ---------------------- |
| `middleware/api/spec/arc-manager/` | `middleware/api/src/middleware/api/business_logic/arc_manager.py` |
| `middleware/api/spec/arc-store/` | `middleware/api/src/middleware/api/arc_store/git_repo.py`, `gitlab_api.py` (deprecated) |
| `middleware/api/spec/document-store/` | `middleware/api/src/middleware/api/document_store/couchdb_client.py` |
| `middleware/api/spec/harvest-management/` | `middleware/api/src/middleware/api/business_logic/harvest_manager.py` |
| `middleware/api/spec/arc-upload/` | `middleware/api/src/middleware/api/api/v3/arcs.py` |
| `middleware/api/spec/harvest-arc-upload/` | `middleware/api/src/middleware/api/api/v3/harvests.py` |
| `spec/` (project-level) | Follow links in **Architecture & Design** above to the affected component. |

---

## 🚀 Recent Work Sessions

### Session 1: ConfigWrapper Primitive Types

- Extended ConfigWrapper to support `int, float, bool, None`
- Added 24 comprehensive tests
- Achieved 86.53% code coverage

### Session 2: Git LFS Setup

- Implemented Git LFS for large SQL files
- Created version-controlled hooks in `scripts/git-hooks/`
- Integrated setup into `scripts/load-env.sh`

### Session 3: Optional Client Certificates

- Made `client_cert_path` and `client_key_path` optional in ApiClient
- Updated validation to check `if cert_path is not None`
- Updated all related tests (26/26 passing)
- Updated configuration validation test

### Session 4: PyInstaller & Scaling Strategy

- Investigated and resolved `TypeError: stat` crash in frozen Python 3.12 environment.
- Identified incompatibility between Pydantic v2's plugin scan and multiple Uvicorn workers in frozen state.
- Decision: Enforce single worker per container; scale horizontally via Kubernetes replicas.
- Improved Docker build by including metadata for `pydantic`, `fastapi`, `uvicorn`, `prompt-toolkit`, and `click`.
- Fixed Celery worker crash caused by missing `prompt_toolkit` metadata.

### Session 5: Architecture Simplification & Robustness

- Removed redundant `couchdb-init` service and `setup-couchdb` CLI command.
- Integrated automatic CouchDB system database initialization into `CouchDBClient.connect`.
- Implemented race-condition-safe database creation in `CouchDBClient` to handle parallel service startups.
- Fixed Pylint protected-access (W0212) issues in `system.py` by adding appropriate public getters to `BusinessLogic`.
- Improved type safety by replacing `Any` with concrete types (`CouchDB`, `Database`) in `CouchDBClient`.
- Cleaned up Helm Chart templates by removing `initContainers` for CouchDB initialization.

### Session 6: Ruff Parity Across Editor/Hook/CI

- Standardized Ruff checks to run against `middleware/` in pre-commit and CI.
- Fixed formatting drift in Markdown-embedded Python snippets (e.g., `middleware/api_client/README.md`).
- Clarified that Ruff failures can be caused by `hatch-vcs` version parsing during `uv run`, and documented how to diagnose it.

### Session 7: Spec-Driven Development Setup

- Introduced Specifica-based spec-driven development (SDD) workflow.
- Created `.agents/skills/` with three skills: `arctrl`, `config-wrapper`, `create-specifica-feature`.
- Created `.github/agents/spec-to-code.agent.md` custom agent for spec-to-code translation.
- Created `spec/principles.md` as the authoritative project foundation contract.
- Created `middleware/api/spec/` with four component-level specs: `arc-manager`, `arc-store`, `document-store`, `harvest-management`.
- Created `docs/ai_workflow.md` documenting the SDD workflow and VS Code integration.
- Updated `AGENTS.md` with Architecture & Design section linking to all specs.

---

Before making changes, consider:

- Should I use `uv` or another tool? → Always `uv`
- Are client certificates required? → No, they're optional
- Should I modify `.git/hooks/` directly? → No, use `scripts/setup-git-lfs.sh`
- What Python version? → 3.12.12
- How to run tests? → `uv run pytest ...`

---

**Last Updated**: 2026-04-20
**Current Branch**: feature/going_sdd
**Maintainer Notes**: Keep this file updated when architectural decisions change
