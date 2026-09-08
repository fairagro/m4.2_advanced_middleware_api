# Project Principles

This repository extends the shared foundation in
[`principles.global.md`](principles.global.md). Read that file first for Values,
Supported development environment, Type Safety, Configuration, Code Quality,
Testing, Security, Spec/Code naming, Python tooling, and Branch strategy.

Do **not** redefine or weaken Supported development environment or Type Safety
here — those sections are owned by `principles.global.md`.

Product stack, module graph, and scaling notes for the Advanced Middleware API
live below. Surface-bar path rows for this product belong in
[`docs/surface-quality-bar.md`](../docs/surface-quality-bar.md) (not here).

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

Package manager: always `uv` (never pip/poetry directly). See also Python
tooling in `principles.global.md`.

---

## Module Dependency Rules

```text
middleware/api/          ← primary API component
middleware/shared/       ← utilities shared across components (ConfigWrapper, models)
middleware/api_client/   ← optional client library for API consumers
```

- `api` may depend on `shared` and `api_client`.
- `shared` must not depend on `api` or `api_client`.
- `api_client` may depend on `shared`; it must not depend on `api`.

---

## Configuration (product)

Shared rules are in `principles.global.md`. In this repo:

- Runtime configuration is read from YAML via `ConfigWrapper`
  (`middleware.shared.config.config_wrapper`).
- **No `os.environ` calls in application code.** Environment variables are
  resolved by `ConfigWrapper` only.
- Every configurable value must have a Pydantic field with a `description`.
- Defaults belong in `Config`, not in application code.
- See the `config-wrapper` skill for the full pattern.

---

## Testing (product layout)

Shared testing expectations are in `principles.global.md`. Layout here:

- Unit tests: `middleware/api/tests/unit/` — instantiate `Config` directly.
- Integration tests: `middleware/api/tests/integration/` — mock at wrapper
  boundary.
- Also: `middleware/shared/tests/`, `middleware/api_client/tests/`.
- Run with `uv run pytest` (scoped paths as needed).

---

## Scaling

- One worker process per container. Scale horizontally via Kubernetes replicas.
- Background tasks (GitLab sync) run in Celery workers, not in the API process.
- ARC objects must not cross process boundaries via pickle — serialize to JSON
  first (they carry .NET interop state).

---

## Spec / Code Naming (product)

- Capability specs live under `openspec/specs/<domain>/` with kebab-case domain
  names that mirror the primary code artifact they describe (e.g. `ArcManager`
  → `openspec/specs/arc-manager/`).
- Behaviour-oriented domains (e.g. `arc-store/`) need not map 1:1 to a class.
- Stable architecture notes may live as `openspec/specs/<domain>/design.md`.
- Keep the **Spec-to-Code Mapping** table in `AGENTS.md` current.

---

## Security (product)

Shared security principles are in `principles.global.md`. In this repo:

- Client certificates are optional but recommended for production.
- SSL verification is enabled by default.
- All inputs are validated at system boundaries by Pydantic.
- No secrets in logs or error messages.

---

## Branch Strategy (product)

This project uses **Trunk-Based Development** with short-lived branches:

| Branch | Purpose | CI behaviour |
| ------ | ------- | ------------ |
| `main` | Trunk — always deployable production state | Final release via `workflow_dispatch` |
| `feature/*` | New features and bug fixes | PR checks; manual pre-release via `workflow_dispatch` |
| `docs/*` | Documentation-only changes | Change detection skips all CI jobs |

- All branches merge into `main` via pull request.
- `feature/*` covers both new functionality and bug fixes; no separate
  `fix/*` or `hotfix/*` branches.
- `docs/*` branches exist solely to skip unnecessary CI; they carry no release
  privilege.
- Long-lived branches other than `main` are not permitted.
