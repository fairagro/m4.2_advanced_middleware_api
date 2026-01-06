# GitHub Copilot Instructions

This file provides context and instructions for GitHub Copilot in this workspace.

## 🚨 Critical Rules - ALWAYS Follow

### Python Package Manager
- **ALWAYS use `uv` for Python commands** - Never use `pip`
- Example: `uv run pytest ...` instead of `python -m pytest`
- Exception: System packages via `apt-get` are fine

### Configuration System
- YAML-based with environment variable overrides
- ConfigWrapper supports: `str | int | float | bool | None`
- Type parsing: `"true"` → `True`, `"123"` → `123`, `"3.14"` → `3.14`
- Empty env strings become `None`

### Client Certificates (OPTIONAL)
- **Client certificates in ApiClient are OPTIONAL** (`Path | None`)
- Both must be provided together or both be `None`
- Validate only if `cert_path is not None`

### Git LFS Setup
- SQL files (`*.sql`) tracked automatically by Git LFS
- Install via `scripts/load-env.sh`, never `git lfs install`
- Version-controlled hooks in `scripts/git-hooks/`

## 📋 Tech Stack

- Python 3.12.12 (REQUIRED)
- FastAPI
- Pydantic V2
- PostgreSQL 15.15
- Docker + Docker Compose
- Git LFS 3.3.0+

## 📁 Key Directories

```
middleware/
  ├── shared/         ConfigWrapper (24 tests, 86.53% coverage)
  ├── api/            FastAPI REST API
  ├── api_client/     HTTP Client (26 tests)
  └── sql_to_arc/     SQL to ARC Converter

scripts/
  ├── load-env.sh    Main entry point (sets up hooks)
  └── setup-git-lfs.sh
```

## 🔧 Essential Commands (with `uv`)

```bash
# Tests
uv run pytest middleware/shared/tests/unit/ -v
uv run pytest middleware/api_client/tests/unit/ -v

# Quality
uv run ruff check .
uv run mypy middleware/

# Setup
source scripts/load-env.sh

# Docker
cd dev_environment && ./start.sh --build
```

## ⚠️ Common Patterns

### When Editing Files
1. Check current state with `read_file`
2. Use `replace_string_in_file` with 3-5 lines context
3. Never modify `.git/` directly
4. Run tests after changes: `uv run pytest`

### Configuration Validation
- Client certs: Optional, check `if cert_path is not None`
- ConfigWrapper: Supports nested dicts and lists with primitives
- ApiClient: Works without certificates (no mTLS required)

## 📞 Questions Before Making Changes

- Python command? → Always `uv`
- Client certificates required? → No, optional
- Modify git hooks directly? → No, use scripts
- Python version? → 3.12.12
- Run tests? → `uv run pytest`

---

**Last Updated**: 2025-12-10
**Branch**: feature/introduce_sql_to_arc
**For more details**: See AGENTS.md in project root
