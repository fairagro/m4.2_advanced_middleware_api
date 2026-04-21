# Project Principles

This document is the authoritative foundation contract for the FAIRagro Advanced
Middleware API. All component specs and design decisions must be consistent with
the constraints stated here.

---

## Values

- **Correctness over speed** — a slow correct ARC is better than a fast broken one.
- **Explicit over implicit** — configuration comes from `Config`, not `os.environ`.
- **Simplicity** — remove abstractions that serve no purpose; add them only when
  duplication becomes a real problem.

---

## Technology Stack

The following technologies are foundational to the middleware API. Component
specs may assume their presence and must not replace them with alternatives
without a project-level decision recorded here.

| Technology | Role |
| ---------- | ---- |
| **FastAPI** | HTTP API framework — all REST endpoints are implemented with FastAPI. |
| **Celery** | Async task queue — background GitLab sync runs as Celery tasks. |
| **CouchDB** | Document store — ARC documents, harvest metadata, and event logs are persisted in CouchDB. |
| **RabbitMQ** | Message broker — Celery uses RabbitMQ to queue and deliver tasks. |

---

## Module Dependency Rules

```text
middleware/api/          ← primary API component
middleware/shared/       ← utilities shared across components (ConfigWrapper, models)
middleware/api_client/   ← optional client library for API consumers
```

- `api` may depend on `shared` and `api_client`.
- `shared` must not depend on `api` or `api_client`.
- `api_client` must not depend on `api` or `shared`.

---

## Configuration

- All runtime configuration is read from a YAML file via `ConfigWrapper`.
- **No `os.environ` calls in application code.** Environment variables are
  resolved by `ConfigWrapper` only.
- Every configurable value must have a Pydantic field with a `description`.
- Defaults belong in `Config`, not in application code.
- See the `config-wrapper` skill for the full pattern.

---

## Type Safety

- All public functions and methods must have full type annotations.
- `dict[str, Any]` and bare `Any` fields are forbidden in `Config` subclasses.
- Concrete Pydantic types for nested configs.
- `SecretStr` for passwords and tokens — call `.get_secret_value()` only at
  the point of use (never log or cast to `str`).

---

## Code Quality

All code must pass:

- `uv run ruff format --check middleware/` — formatting
- `uv run ruff check middleware/` — linting
- `uv run mypy middleware/` — static type checking
- `uv run pylint middleware/` — style and code smells
- `uv run bandit -r middleware/ -c .bandit` — security (low findings logged, medium/high fail)

**Suppression comments** (`# noqa`, `# type: ignore`, `# pylint: disable`) are
a last resort. A real fix is always preferred.

---

## Testing

- Unit tests: `middleware/api/tests/unit/` — instantiate `Config` directly.
- Integration tests: `middleware/api/tests/integration/` — mock at wrapper boundary.
- Tests are run with `uv run pytest middleware/ -v`.
- Every public behaviour that can fail must have at least one test.

---

## Scaling

- One worker process per container. Scale horizontally via Kubernetes replicas.
- Background tasks (GitLab sync) run in Celery workers, not in the API process.
- ARC objects must not cross process boundaries via pickle — serialize to JSON
  first (they carry .NET interop state).

---

## Spec / Code Naming

- Spec folder names use kebab-case and must mirror the primary code name they
  describe. A spec for `ArcManager` lives in `arc-manager/`; a spec for
  `HarvestManager` lives in `harvest-manager/` (kebab-case of the class name).
- When a spec covers a behaviour rather than a single class (e.g. `arc-store/`),
  the folder name describes that behaviour; it is acceptable if there is no
  exact 1:1 class match.
- The mapping from spec folders to source files must be maintained in the
  **Spec-to-Code Mapping** table in `AGENTS.md`.

---

## Security

- Client certificates are optional but recommended for production.
- SSL verification is enabled by default.
- All inputs are validated at system boundaries by Pydantic.
- No secrets in logs or error messages.

---

## Branch Strategy

This project uses **Trunk-Based Development** with short-lived branches:

| Branch | Purpose | CI behaviour |
| ------ | ------- | ------------ |
| `main` | Trunk — always deployable production state | Final release via `workflow_dispatch` |
| `feature/*` | New features and bug fixes | PR checks; manual pre-release via `workflow_dispatch` |
| `docs/*` | Documentation-only changes | Change detection skips all CI jobs |

**Rules:**

- All branches merge into `main` via pull request.
- `feature/*` covers both new functionality and bug fixes; no separate `fix/*` or `hotfix/*` branches.
- `docs/*` branches exist solely to skip unnecessary CI; they carry no release privilege.
- Long-lived branches other than `main` are not permitted.
