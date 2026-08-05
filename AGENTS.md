# AGENTS.md - Instructions for AI Assistants

This file contains critical context about the FAIRagro Advanced Middleware API
project for AI assistants (GitHub Copilot, Claude, etc.).

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
└── skills/                # Project Agent Skills (agentskills.io)
    ├── arctrl/            # arctrl Python library reference
    └── config-wrapper/    # ConfigWrapper / ConfigBase pattern

.cursor/skills/            # OpenSpec-generated Cursor skills (openspec update)
.github/skills/            # OpenSpec-generated Copilot skills (openspec update)

docs/
└── ai_workflow.md         # AI agent workflow documentation

openspec/                  # OpenSpec source of truth + change proposals
├── principles.md          # Foundation contract, project values
├── config.yaml            # OpenSpec project context and rules
└── specs/                 # Capability specs (current behaviour)
    ├── arc-manager/
    ├── arc-store/
    ├── document-store/
    ├── harvest-manager/
    └── …

middleware/
├── shared/                 # Shared utilities & configuration
│   └── config/
│       └── config_wrapper.py    # ConfigWrapper with primitive types (24 tests, 86.53% coverage)
├── api/                    # FastAPI REST API
│   └── src/middleware/api/
├── api_client/            # Client library for API
│   └── config.py          # Optional certificate support (26 tests)

scripts/
├── load-env.sh                    # Environment setup (sourced from ~/.bashrc)
├── setup-git-lfs.sh               # Git LFS hooks (standalone / re-runnable)
├── devcontainer-post-create.sh    # Dev Container + local one-time setup
└── git-hooks/                     # Version-controlled hooks
    ├── pre-push                   # Combined: Git LFS + pre-commit
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

1. `scripts/devcontainer-post-create.sh` (or Dev Container postCreate) installs
   pre-commit and calls `scripts/setup-git-lfs.sh`
2. Git LFS hooks are installed from `scripts/git-hooks/`
3. Hooks are version-controlled, not just in `.git/hooks/`
4. Re-run LFS hooks alone with `scripts/setup-git-lfs.sh` when needed

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

Agents are expected to maintain high code quality by addressing issues reported
by the project's configured tools: **Ruff, Pylance, MyPy, Pylint, and Bandit**.

- **Automatic Fixes**: Actively check for and fix code smells, warnings, and
  notices.
- **Real Fixes vs. Suppression**: Issues must be resolved with actual code
  changes. Using comments to suppress warnings (e.g., `# noqa`,
  `# type: ignore`, `# pylint: disable`) is an **option of last resort**.
- **When to Suppress**: Only suppress if a fix is technically impossible or
  would result in unnecessarily complex or unreadable code.
- **Comprehensive Coverage**: Fix all reported issues, including low-severity
  notices and warnings, not just critical errors.

### Ruff Execution Consistency

- Keep Ruff behavior identical in Cursor/VS Code, pre-commit, and GitHub Actions
  by using the same scope (`middleware/`), the same root config
  (`pyproject.toml`), and the same binary (`.venv/bin/ruff` via `uv run ruff`).
- Editor: `.vscode/settings.json` must set `ruff.path` to
  `${workspaceFolder}/.venv/bin/ruff`. Do **not** set it to `["uv", "run",
  "ruff"]` — `ruff.path` entries are treated as executables, so `uv` would be
  launched as Ruff and the Problems tab stays empty.
- Lint diagnostics appear in Problems; **format** drift does not (Ruff applies
  format via Format on Save / `ruff format`). Before commit, run the same
  checks as CI: `uv run ruff format --check --diff middleware/` and
  `uv run ruff check middleware/` (or `./scripts/quality-fix.sh` then
  pre-commit).
- Avoid partially staging a Python file (`MM` in `git status`): pre-commit may
  auto-format the index, then roll back when the stash conflicts with unstaged
  edits — leaving format failures invisible in the editor.
- If `uv run ruff ...` fails before Ruff starts and shows
  `packaging.version.InvalidVersion` from `hatch-vcs`, the failure is in
  package version resolution, not Ruff itself.
- In that case, verify `tool.hatch.version.raw-options` in
  `middleware/*/pyproject.toml` can parse repository tags used by CI/release
  workflows.

## 📚 File Modifications Pattern

When editing files:

1. **Always check current state** - Use `read_file` to see current content
2. **Use `replace_string_in_file`** - Include 3-5 lines of context before/after
3. **Never modify `.git/` directly** - Use scripts instead
4. **Test after changes** - Always run relevant tests with `uv run pytest`

## 🏗️ Architecture & Design

**Read [`openspec/principles.md`](openspec/principles.md) first.** It defines module
dependency rules, configuration constraints, typing rules, and code quality
requirements. Do not restate what is there.

Specs follow [OpenSpec](https://openspec.dev/): current behaviour lives in
`openspec/specs/<domain>/`; proposed work lives in `openspec/changes/`.
Use `/opsx-propose` for new work. Stable architecture notes may accompany a
capability as `design.md`. Project conventions for agents live in
`openspec/config.yaml` and this file (Spec-to-Code Mapping).

Before generating or modifying code, read the relevant specs:

**Foundation / cross-cutting:**

- **[`openspec/principles.md`](openspec/principles.md)** — Authoritative project principles (start here).
- **[`openspec/specs/ci-cd/`](openspec/specs/ci-cd/)** — GitHub Actions: PR validation, Docker/Helm releases, CodeQL scanning.

**API capabilities** (`openspec/specs/`):

- **[`openspec/specs/arc-upload/`](openspec/specs/arc-upload/)** — HTTP contract
  for `POST /v3/arcs`: standalone ARC submission (rdi from request body);
  content-hash idempotent, retry-safe.
- **[`openspec/specs/harvest-arc-upload/`](openspec/specs/harvest-arc-upload/)**
  — HTTP contract for `POST /v3/harvests/{harvest_id}/arcs`: harvest-scoped
  submission; identical re-submit → `200`, conflicting content → `409`.
- **[`openspec/specs/arc-manager/`](openspec/specs/arc-manager/)** —
  `ArcManager.create_or_update_arc` business logic: CouchDB storage,
  content-hash + harvest-scoped idempotency, Celery dispatch. Shared by both
  upload endpoints and accessible from the worker context.
- **[`openspec/specs/arc-store/`](openspec/specs/arc-store/)** — `ArcStore`
  Git-backend interface: `GitRepo` (primary) and `GitlabApi` (deprecated),
  error classification, and credential injection.
- **[`openspec/specs/document-store/`](openspec/specs/document-store/)** —
  CouchDB persistence layer, race-condition-safe initialization, and
  content-hash idempotency.
- **[`openspec/specs/harvest-manager/`](openspec/specs/harvest-manager/)** —
  Harvest run lifecycle, ownership validation, and progress tracking.
- **[`openspec/specs/admission-control/`](openspec/specs/admission-control/)** —
  Process-local concurrent request admission: at capacity → `503` +
  `Retry-After` (probes exempt).

**API Client capabilities:**

- **[`openspec/specs/harvest-client/`](openspec/specs/harvest-client/)** —
  Harvest lifecycle: parallel ARC submission, per-item error collection
  (`HarvestError`, `HarvestErrorType`), typed statistics (`HarvestStatistics`),
  and compatibility shim for issue #240.

**Shared capabilities:**

- **[`openspec/specs/harvest-report/`](openspec/specs/harvest-report/)** —
  Format-neutral harvest-run accumulator with repository scope counting and
  pluggable serializers (JSON-LD first): `HarvestReport`, `RepositoryScope`,
  `RepositoryReport`, `HarvestIssue`.

For the AI agent workflow documentation, see [`docs/ai_workflow.md`](docs/ai_workflow.md).

### Spec-to-Code Mapping

This table maps each OpenSpec domain to the primary source file(s) it describes.
Agents (`/opsx-apply` and default Agent mode) use it to locate affected code.

| Spec domain | Primary source file(s) |
| ----------- | ---------------------- |
| `openspec/specs/arc-manager/` | `middleware/api/src/middleware/api/business_logic/arc_manager.py` |
| `openspec/specs/arc-store/` | `middleware/api/src/middleware/api/arc_store/git_repo.py`, `gitlab_api.py` (deprecated) |
| `openspec/specs/document-store/` | `middleware/api/src/middleware/api/document_store/couchdb_client.py`, `couchdb.py` |
| `openspec/specs/harvest-manager/` | `middleware/api/src/middleware/api/business_logic/harvest_manager.py` |
| `openspec/specs/arc-upload/` | `middleware/api/src/middleware/api/api/v3/arcs.py` |
| `openspec/specs/harvest-arc-upload/` | `middleware/api/src/middleware/api/api/v3/harvests.py` |
| `openspec/specs/admission-control/` | `middleware/api/src/middleware/api/api/admission_control.py`, `fastapi_app.py` |
| `openspec/specs/harvest-client/` | `middleware/api_client/src/middleware/api_client/api_client.py`, `models.py` |
| `openspec/specs/harvest-report/` | `middleware/shared/src/middleware/shared/report/`, `ns/harvest-report/` |
| `openspec/specs/ci-cd/` | `.github/workflows/` (see domain design for workflow files) |

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
- Clarified that Ruff failures can be caused by `hatch-vcs` version parsing
  during `uv run`, and documented how to diagnose it.

### Session 7: Spec-Driven Development Setup

- Introduced Specifica-based SDD, later migrated to OpenSpec (Session 8).
- Created `.agents/skills/` with `arctrl` and `config-wrapper`.
- Created `docs/ai_workflow.md` documenting the SDD workflow and VS Code integration.

### Session 8: OpenSpec Migration

- Extended Dev Container with Node.js 20.x and pinned `@fission-ai/openspec` CLI.
- Initialized OpenSpec (`openspec/`) with Cursor + GitHub Copilot tooling.
- Seeded baseline capability specs from Specifica into `openspec/specs/` (curated rewrite).
- Relocated principles to `openspec/principles.md`; removed Specifica paths.

---

Before making changes, consider:

- Should I use `uv` or another tool? → Always `uv`
- Are client certificates required? → No, they're optional
- Should I modify `.git/hooks/` directly? → No, use `scripts/setup-git-lfs.sh`
- What Python version? → 3.12.12
- How to run tests? → `uv run pytest ...`
- Where do specs live? → `openspec/specs/<domain>/` (propose changes via `/opsx-propose`)

---

**Last Updated**: 2026-07-29
**Current Branch**: feature/going_sdd
**Maintainer Notes**: Keep this file updated when architectural decisions change
