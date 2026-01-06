# AGENTS.md - Instructions for AI Assistants

This file contains critical context about the FAIRagro Advanced Middleware API project for AI assistants (GitHub Copilot, Claude, etc.).

## 📋 Tech Stack

| Component | Version | Details |
|-----------|---------|---------|
| Python | 3.12.12 | Primary language |
| FastAPI | Latest | REST API framework |
| Pydantic | V2 | Configuration validation |
| PostgreSQL | 15.15 | Database |
| Docker | Latest | Containerization |
| Git LFS | 3.3.0+ | Large file storage |
| uv | Latest | Python package manager |

## 📁 Project Structure

```text
middleware/
├── shared/                 # Shared utilities & configuration
│   └── config/
│       └── config_wrapper.py    # ConfigWrapper with primitive types (24 tests, 86.53% coverage)
├── api/                    # FastAPI REST API
│   └── src/middleware/api/
├── api_client/            # Client library for API
│   └── config.py          # Optional certificate support (26 tests)
├── sql_to_arc/            # SQL to ARC converter
│   └── config.py          # Uses ApiClientConfig

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

# Install all dependecies
uv sync --dev --all-packages
```

### Development Environment for sql_to_arc

```bash
# Start dev environment
cd dev_environment
./start.sh --build

# View logs
docker compose logs -f

# Cleanup
docker compose down
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
  sql_to_arc:         # SQL to ARC converter
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

## 📚 File Modifications Pattern

When editing files:

1. **Always check current state** - Use `read_file` to see current content
2. **Use `replace_string_in_file`** - Include 3-5 lines of context before/after
3. **Never modify `.git/` directly** - Use scripts instead
4. **Test after changes** - Always run relevant tests with `uv run pytest`

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

## 📞 Questions to Ask

Before making changes, consider:

- Should I use `uv` or another tool? → Always `uv`
- Are client certificates required? → No, they're optional
- Should I modify `.git/hooks/` directly? → No, use `scripts/setup-git-lfs.sh`
- What Python version? → 3.12.12
- How to run tests? → `uv run pytest ...`

---

**Last Updated**: 2025-12-10
**Current Branch**: feature/introduce_sql_to_arc
**Maintainer Notes**: Keep this file updated when architectural decisions change
