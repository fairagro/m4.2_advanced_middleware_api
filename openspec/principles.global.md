# Shared project principles

Canonical engineering foundation for FAIRagro m4.2 middleware product repos and this Devinfra repo. Synced as
`openspec/principles.global.md` — do **not** hand-edit in consumers. Repo-local extensions belong in
`openspec/principles.md`.

All component specs and design decisions must stay consistent with the constraints here. Product stack, module graphs,
and scaling notes live in the local `principles.md` (or product capability specs), not in this file.

### Synced `.global` + product overlay

When a shared file needs a product-specific companion that sync must not wipe, use this naming pair:

| Role                                   | Name shape                                                                                                       | Sync                                                                    |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Fleet SoT (identical in every product) | `*.global` / `*.global.*` (e.g. `principles.global.md`, `surface-quality-bar.global.md`, `.importlinter.global`) | On `docs/synced-paths.yaml` **`allow`** — do not hand-edit in consumers |
| Product extension / overlay            | Same basename **without** `.global` (e.g. `principles.md`, `surface-quality-bar.md`, `.importlinter`)            | On **`overlays`** (never overwritten by sync)                           |

Do **not** invent alternate suffixes such as `.product` for this split. Other overlay styles (env/CI inputs, nested
`.gitignore`, verbatim-only fragments with no product twin) stay as documented in `docs/sync.md`.

---

## Values

- **Correctness over speed** — a slow correct result is better than a fast broken one.
- **Explicit over implicit** — configuration comes from the project's config model, not direct `os.environ` in
  application code.
- **Simplicity** — prefer the smallest readable change that meets the real requirement. Keep complexity as low as needed
  (not lower than correctness requires, not higher “for later”). Add an abstraction only when it removes real
  duplication, clarifies a stable boundary, or makes the call site easier to verify — not for a single call site or
  speculative reuse. Delete unused structure rather than expanding it.
- **Supported environment first** — the Linux Dev Container is the supported way to run the repo. Do not design or
  review for macOS, Windows, Homebrew, or other host package layouts. Running scripts on a bare Linux workstation
  without the Dev Container is possible but unofficial; GitHub Actions Linux is supported for CI. Match the **surface
  quality bar**: product / domain code must hold contracts real callers hit; **shared Devinfra scripts** (`scripts/`
  except agent CLI) are judged on the documented Dev Container / contributor / CI happy path; **agent plumbing**
  (`scripts/ai/`, skill wiring) on the default skill/CLI happy path — not every exotic edge case (see
  `docs/ai_review_policy.md` Surface quality bar and `docs/surface-quality-bar.global.md`).

---

## Configuration

- Runtime configuration is read through the project's config wrapper / config model (not scattered `os.environ` reads).
- **No `os.environ` calls in application code.** Environment variables are resolved only inside that config layer.
- Every configurable value must have a typed field with a `description` (typically Pydantic).
- Defaults belong in the config model, not buried in application code.

---

## Type Safety

- All public functions and methods must have full type annotations.
- Use the most precise type that is actually true (`list[str]`, a concrete class, `TypedDict` / Pydantic model — not
  `list[Any]` or `Sequence[object]`).
- `Any` and `object` only when the value is genuinely unconstrained and cannot be narrowed. `dict[str, Any]` and bare
  `Any` fields are forbidden in config model subclasses.
- Do not introduce a type alias whose meaning is `Any`, `object`, or another equally wide type so the annotation looks
  precise.
- Concrete Pydantic types for nested configs.
- `SecretStr` for passwords and tokens — call `.get_secret_value()` only at the point of use (never log or cast to
  `str`).
- Do **not** widen a type to silence a checker or review (`T` → `T | None`, `Any`, `dict[str, Any]`). Narrow at the
  source.
- Do **not** add `if x is None` when the annotation, Pydantic model, or config wrapper already excludes `None`. If
  `None` is required, change the producing API and every caller — no mid-pipeline guards.

### Function signatures and `**kwargs`

- Name every parameter the caller is expected to pass — in tests, production code, and monkey-patches that mirror
  upstream APIs.
- Do **not** replace known parameters with `**kwargs` just to satisfy linters or shorten signatures.
- `**kwargs` / `**_ignored` is allowed only for genuinely open-ended extension points (e.g. forwarding extras from a
  third-party library whose future keyword arguments are not fixed at compile time).
- When a signature must match an upstream definition, mirror its explicit parameters and reserve `**kwargs` for the same
  passthrough role upstream uses.

---

## Python tooling

- **`uv` only** — install, sync, lock, run, and tool invocation for Python use **`uv`** / **`uvx`** exclusively
  (`uv sync`, `uv run …`, `uv add`, `uv lock`, `uv python`, `uv tool`).
- **Do not use `pip`, `pip-tools`, `poetry`, `pipenv`, or bare `python -m pip`** for project or CI dependency
  management. Do not document or suggest those as alternatives.
- Project dependencies and Python CLIs invoked from hooks/scripts belong in `pyproject.toml` (and the lockfile) and are
  run via `uv run` (or an equivalent `uv`-managed environment), not a separately pip-installed global site-packages.
- **One pin source:** exact Python (and other toolchain) versions live in `versions.env`. `.python-version` is derived
  from that and may drift — do not add further pins in `pyproject.toml` (no `tool.mypy.python_version`, no
  `tool.ruff.target-version`, no patch-exact `requires-python` floor). `requires-python` MAY be a compatible **range**
  (e.g. `>=3.12`). Let ruff infer from that range; let mypy follow the running interpreter selected via uv /
  `.python-version`.

---

## Code Quality

Product application code under `middleware/` must pass via `uv run`. Prefer shared synced fragments when present
(`ruff.toml`, `mypy.ini`, `.pylintrc`, `.bandit`); otherwise use the project's equivalent config (e.g. root
`pyproject.toml` tool tables). Do not invent a second quality policy channel. Example invocations with shared fragments:

- `uv run ruff format --check --config ruff.toml middleware/` — formatting
- `uv run ruff check --config ruff.toml middleware/` — linting
- `uv run mypy --config-file mypy.ini middleware/` — static type checking
- `uv run pylint --rcfile .pylintrc middleware/` — style and code smells
- `uv run bandit -r middleware/ -c .bandit -ll` — security (hooks: MEDIUM+ only via `-ll`). CI may omit `-ll` to log LOW
  while still failing only on MEDIUM/HIGH — same fail bar; see `docs/quality.md` when that file is synced
- `uv run vulture middleware/ --min-confidence 100` — unused definitions (hooks + CI; no IDE gate; no synced whitelist;
  see `docs/quality.md`)
- `./scripts/run-import-linter.sh` — import contracts (synced `.importlinter.global` baseline + optional `.importlinter`
  overlay; hooks + CI; no IDE gate; see `docs/quality.md`)

Markdown must pass Prettier formatting and markdownlint (`.markdownlint.json` disables rules that fight Prettier).
Typical scripts (see `package.json` where present):

- `npm run format:md` / `npm run format:md:check` — Prettier write / check for `**/*.{md,mdc}`
- `npm run lint:md` — `markdownlint-cli2`

After OpenSpec or other bulk Markdown edits: format first, then lint; remaining markdownlint findings must be fixed by
hand (do not expand ignore lists to hide them).

Dockerfiles must pass **hadolint** (Dev Container / CI provide `hadolint`). Prefer fixing the Dockerfile over
suppressions; document any necessary ignore with a one-line reason.

**Suppression comments** (`# noqa`, `# type: ignore`, `# pylint: disable`, hadolint ignores) are a last resort. A real
fix is always preferred.

### Environment parity (IDE, hooks, CI)

Every shared quality gate above MUST run with the **same shared config file(s)** and produce the **same pass/fail
outcome** (same policy findings) in:

1. the **IDE** (workspace / extension settings), where a maintained integration exists;
2. **pre-commit** (commit stage) and **pre-push** when that tool is a push gate;
3. **GitHub** reusable / caller quality pipelines.

Invocations MAY pass the config-file path, analysis target paths, and documented product path overlays (e.g. `MYPYPATH`,
pylint `--source-roots`). They MUST NOT restate rule/severity/version policy as extra CLI or IDE flags when that policy
is expressible in the shared config file. If a tool has no supported IDE integration, document “hooks + CI only” for
that tool — do not invent a second config channel. Details: `docs/quality.md` when synced.

This Devinfra repository has no product `middleware/` packages; the Python gates above apply when working in product
consumers. Markdown and hadolint gates apply here and in consumers that ship those files.

---

## Import policy

Product application code under `middleware/` (and tests that import that code) MUST keep an acyclic import DAG. Do
**not** paper over a bad graph with path hacks or deferred imports — **cut modules** so every runtime edge is a normal
top-level absolute import.

1. **Never** mutate import paths at runtime to make a module resolvable (`sys.path` inserts, rewriting `__path__`,
   project-root shims that redirect to `src/`, and equivalents).
2. **Imports MUST run at module level** — not inside functions, methods, or conditional runtime blocks.
3. **`if TYPE_CHECKING:` is allowed** for type-only imports (annotations). It is **not** a license for cyclic
   **runtime** edges — cut modules instead.
4. **No relative imports** — use absolute imports (`middleware.<package>…`).
5. **Never** use deferred / lazy imports **for the purpose of breaking import cycles** (including lazy `__getattr__`
   re-exports used only to hide a bad graph).
6. **Do** split modules so the dependency DAG is acyclic and every **runtime** edge is a normal top-level absolute
   import.
7. **Exceptions** to (1)/(2)/(4)/(5)/(6) require user agreement plus an inline comment and/or a principles note naming
   the exception and why.

### Package `__init__.py`

Curated public `__all__` with **eager absolute** re-exports is allowed when the subgraph is already acyclic. Prefer a
thin docstring-only `__init__` when there is no public surface. Lazy / `__getattr__` re-exports used only to hide cycles
are forbidden.

### Registration-only imports

Prefer a side-effect module imported absolutely at module level (no function-body imports).

### Monorepo src-layout shadowing

Prefer rename/move or a documented static layout. Runtime shims remain forbidden.

### Tests

Rules (2)/(4)/(5)/(6) apply equally to unit tests that import application code.

Product-only module graphs and stack tables belong in local `principles.md` / product specs — not in this file.

---

## Testing

- Every public behaviour that can fail must have at least one test.
- Prefer tests that lock **real** behaviour over tests that encode states the types already forbid.
- Run tests with `uv run pytest` scoped to the affected package tree.

---

## Supported development environment

The **supported** way to develop and run repo scripts (`scripts/`, `gh` wrapper, quality hooks, token helpers) is the
**Linux Dev Container** defined for that repository. GitHub Actions Linux runners are supported for CI.

The following are **out of scope** for product code, scripts, and AI reviews:

- macOS, Homebrew, Windows, or other host package layouts
- `gh` / tools installed only on a custom host `PATH` (e.g. Homebrew prefixes) that the Dev Container does not use
- Making wrappers portable to unofficial bare-metal Linux installs

A Linux workstation without the Dev Container may still run some scripts; that path is **not** officially supported. Do
not add complexity to accommodate it. The Dev Container exists to remove host-environment differences.

Finders must not comment on “Homebrew / local install / macOS / Windows PATH” breakage. Fixers must **dismiss** those
findings (practicality **None** — quote this section).

---

## Spec / Code Naming

- Capability specs live under `openspec/specs/<domain>/` with kebab-case domain names that mirror the primary code
  artifact or behaviour they describe.
- When a spec covers a behaviour rather than a single class, the folder name describes that behaviour; it is acceptable
  if there is no exact 1:1 class match.
- Stable architecture decisions may live alongside the capability as `openspec/specs/<domain>/design.md`. Change-scoped
  design belongs in `openspec/changes/<change>/design.md`.
- Products that maintain a Spec-to-Code Mapping table (often in `AGENTS.md`) must keep it accurate; that table is
  product-local.

---

## Security

- All inputs are validated at system boundaries (typically Pydantic).
- No secrets in logs or error messages.
- SSL verification is enabled by default unless a documented exception exists.

---

## Branch Strategy

These projects use **Trunk-Based Development** with short-lived branches. Prefixes are **CI channels** (not GitHub issue
types). Fine-grained job skips stay on path / change detection — do not invent per-kind prefixes (`test/`, `scripts/`,
…).

| Branch    | Purpose                                                          | CI behaviour                                          |
| --------- | ---------------------------------------------------------------- | ----------------------------------------------------- |
| `main`    | Trunk — always deployable                                        | Final release via `workflow_dispatch` when applicable |
| `build/*` | Product image/app work (any issue type)                          | PR checks; optional Pre Release / RC via dispatch     |
| `ci/*`    | Shared CI/tooling (scripts, Dev Container, quality, those tests) | PR checks; no product-image Pre Release               |
| `docs/*`  | Documentation-only changes                                       | Change detection may skip unnecessary CI jobs         |
| `chore/*` | Sync / bots                                                      | Never Pre Release                                     |

- All branches merge into `main` via pull request.
- Issue-driven work uses `{channel}/issue-<n>-<slug>` (issue number always present). Unclear scope → `build/`.
- No separate `fix/*` / `hotfix/*` / `feature/*` work-branch convention — `build/*` replaced historical `feature/*` for
  RC.
- Long-lived branches other than `main` are not permitted.
