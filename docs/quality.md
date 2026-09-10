# Shared quality tooling

Commit-stage and pre-push quality via [`pre-commit`](https://pre-commit.com). Canonical files live in this Devinfra repo
for sync into product consumers (`middleware/` package root — see [path conventions](conventions.md)).

## Script environments

Not every file under `scripts/` is Dev Container-only. Personal-token helpers are; quality runners are not.

| Script / tree                         | Environment            | Notes                                                                                                                                                    |
| ------------------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-check.sh` / `quality-fix.sh` | Host or Dev Container  | Needs `uv`. Commit-stage also runs `npm run lint:md` (Node/`npm`; host: `npm install`). On the host, set `GITGUARDIAN_API_KEY` for ggshield if required. |
| `run-container-structure-test.sh`     | Host or Dev Container  | Needs Docker + `container-structure-test`                                                                                                                |
| `setup-git-hooks.sh` / `git-hooks/`   | Host or Dev Container  | Copies `pre-push` into `.git/hooks/`; no `git-lfs` required                                                                                              |
| `load-versions-env.sh`                | Host or Dev Container  | Reads `versions.env`, writes `.python-version`                                                                                                           |
| `scripts/ai/` (`m42-ai`)              | Host or Dev Container  | uv workspace member; `uv sync` then `uv run m42-ai` (needs `gh` + auth)                                                                                  |
| `dev-tokens.sh` / `set-dev-tokens.sh` | **Dev Container only** | Store: `/commandhistory/tokens.env`                                                                                                                      |
| `scripts/bin/gh`, `scripts/bin/git`   | **Dev Container only** | On `PATH` via `remoteEnv`; load the token store                                                                                                          |
| `devcontainer-post-create.sh`         | **Dev Container only** | Invoked from `devcontainer.json`                                                                                                                         |

Supported day-to-day development remains the Linux Dev Container ([principles](../openspec/principles.global.md)). Host
checkouts may run the **host-or-DC** scripts above; they do not get the personal-token store or PATH wrappers — use
tokens already in your environment (e.g. exported from `~/.bashrc`) or `gh auth` as you prefer.

## Environment parity (IDE, hooks, CI)

Shared quality tools must agree across three surfaces for the same tree and toolchain pins (`versions.env` / `uv sync` /
Node as documented):

| Environment   | How it runs                                                                   | Config source                                |
| ------------- | ----------------------------------------------------------------------------- | -------------------------------------------- |
| **IDE**       | [`.vscode/settings.json`](../.vscode/settings.json) + recommended extensions  | Same fragment / config files as hooks and CI |
| **Hooks**     | pre-commit (commit) / pre-push stage; `./scripts/quality-check.sh`            | `.pre-commit-config.yaml` → shared configs   |
| **GitHub CI** | [`reusable-code-quality.yml`](../.github/workflows/reusable-code-quality.yml) | Same shared configs                          |

**Matching results** means the same pass/fail gate and the same policy findings (rule id + location). Log formatting may
differ (IDE diagnostics vs CLI). **Bandit exception:** the fail bar is the same (MEDIUM/HIGH fail; LOW never fails), but
CI may **log** LOW findings while hooks suppress them with `-ll` — see the Bandit note below.

**Minimal CLI / IDE args:** pass only the config-file path (when the tool does not auto-discover it), target paths, and
documented product path overlays (`MYPYPATH`, pylint `--source-roots`). Do not restate line length, rule selects, ignore
lists, or similar policy on the command line when the shared config file already defines them.

| Tool                    | IDE                                              | Hooks             | CI                              | Notes                                                               |
| ----------------------- | ------------------------------------------------ | ----------------- | ------------------------------- | ------------------------------------------------------------------- |
| Ruff format/lint        | yes (`ruff.toml`)                                | yes               | yes                             | Primary IDE Python lint/format                                      |
| Prettier / markdownlint | yes (Prettier formatter; markdownlint extension) | yes               | via commit-stage / docs scripts | Shared `.markdownlint*` + Prettier                                  |
| Mypy                    | **hooks + CI only**                              | yes (`mypy.ini`)  | yes                             | No shared IDE mypy settings — do not add a second config            |
| Pylint                  | **hooks + CI only**                              | yes (`.pylintrc`) | yes                             | Same as Mypy                                                        |
| Bandit                  | **hooks + CI only**                              | yes (`.bandit`)   | yes                             | Medium/high fail; see Bandit note below                             |
| pytest                  | IDE discovers tests where configured             | pre-push          | yes                             | Product `middleware/` vs Devinfra `scripts/ai` paths differ by repo |

**Bandit severity (named exception):** `.bandit` has no fail-on-severity key. Hooks use Bandit’s `-ll` (report MEDIUM+
only). CI runs without `-ll`, logs all severities (JSON + wrapper), and still fails only on MEDIUM/HIGH — same fail bar
as hooks, matching [principles Code Quality](../openspec/principles.global.md#code-quality). Do not reintroduce a second
fail policy only on one surface.

## Files

| Path                                                | Role                                                                                         |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `.pre-commit-config.yaml`                           | Commit-stage + pre-push hook skeleton                                                        |
| `ruff.toml`                                         | Shared Ruff lint/format (product sync; not Devinfra `[project]`)                             |
| `mypy.ini`                                          | Shared Mypy strictness (path overlays via `MYPYPATH` / hook env — see below)                 |
| `.pylintrc`                                         | Shared Pylint (path overlays via `--source-roots` on hook/CI — see below)                    |
| `scripts/quality-check.sh`                          | Run **commit-stage** hooks only (check)                                                      |
| `scripts/quality-fix.sh`                            | Run commit-stage **autofix** hooks only                                                      |
| `scripts/run-container-structure-test.sh`           | Templated Docker build + `container-structure-test`                                          |
| `scripts/setup-git-hooks.sh`                        | Install project `pre-push` from `scripts/git-hooks/`                                         |
| `scripts/git-hooks/`                                | Version-controlled `pre-push` (pre-commit pre-push stage)                                    |
| `.bandit`                                           | Bandit config (`bandit -c .bandit`)                                                          |
| `.markdownlint.json` (+ ignore / cli2)              | Markdownlint (also used by the markdownlint hook)                                            |
| [`.vscode/settings.json`](../.vscode/settings.json) | Shared IDE baseline (interpreter, Ruff, pytest, Prettier); products extend for `middleware/` |

## Shared Python quality fragments (B2)

Product repos historically kept large `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` blocks in root `pyproject.toml`.
Canonical copies live here as **fragment files** so sync (#13) can overwrite them without replacing product `[project]`
/ uv workspace sections.

| Sync into products | Keep product-local                                                                    |
| ------------------ | ------------------------------------------------------------------------------------- |
| `ruff.toml`        | Root `pyproject.toml` `[project]`, `[tool.uv.*]`, deps                                |
| `mypy.ini`         | Import-path overlays via product hook/CI **env** (e.g. `MYPYPATH`), not `pyproject`   |
| `.pylintrc`        | Import-path overlays via product hook/CI **args** (e.g. `--source-roots=…`), not edit |
| `.bandit`          | pytest / coverage tool tables (unless later unified)                                  |

Shared hooks and reusable CI invoke `mypy --config-file mypy.ini` and `pylint --rcfile .pylintrc`. Those flags mean
product `[tool.mypy]` / `[tool.pylint.*]` in `pyproject.toml` are **ignored**. Do **not** put path overlays into the
synced fragments either — sync (#13) overwrites them. Override on the **product** pre-commit entry/args or CI env
instead (examples in `mypy.ini` / `.pylintrc` headers).

**Not** in the product quality sync set: `scripts/ai/pyproject.toml` (Devinfra `m42-ai-gh` package manifest only).

After sync, products should **remove** duplicated `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` from root
`pyproject.toml` so the fragments are the single tool config. First adoption smoke is expected via sync / product PRs
([#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)), not in the Devinfra MVP PR
([#28](https://github.com/fairagro/m4.2_middleware_devinfra/issues/28)).

Shared **app Dockerfile** base + product-local last stage lives in this repo as
[`docker/Dockerfile.product-app.base`](../docker/Dockerfile.product-app.base) with Bake examples under
[`docker/examples/`](../docker/examples/). Sync the **base** into products; keep the last stage and `docker-bake.hcl`
product-local. Reusable build/release are **Bake-only** (no monolith Dockerfile) — see
[`docs/ci.md`](ci.md#product-app-images-bake-base--last-stage). Adoption:
[#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13) / product Wave C (issue
[#36](https://github.com/fairagro/m4.2_middleware_devinfra/issues/36)).

## IDE (workspace settings)

[`.vscode/settings.json`](../.vscode/settings.json) is part of the shared Devinfra surface (host + Dev Container). It
points the Python extension at the root `.venv` from `uv sync`, configures Ruff via `ruff.toml` like pre-commit/CI,
discovers `scripts/ai` tests, and sets Prettier as default formatter for Markdown/JSON/YAML. Product repos should keep
the same interpreter/Ruff/Prettier contract and add local `python.analysis.extraPaths` (and Helm/SOPS associations) for
their `middleware/` packages — do not copy product-only paths back into this file.

Mypy, Pylint, and Bandit stay **hooks + CI only** in the shared baseline (see
[Environment parity](#environment-parity-ide-hooks-ci)) — do not add product-local IDE settings that invent a second
config for those tools.

### Commit stage

```bash
uv sync
npm install   # host clones needing local markdownlint/prettier; skip if tools are global
uv run pre-commit install --hook-type pre-commit
```

Typical place: Dev Container **postCreate** (`scripts/devcontainer-post-create.sh`). These hooks are **not** files under
`scripts/git-hooks/`.

### Pre-push (quality stage)

```bash
./scripts/setup-git-hooks.sh
```

Copies `scripts/git-hooks/pre-push` into `.git/hooks/`. Does **not** require or install Git LFS. Invoked from Dev
Container postCreate, or once after clone.

On `git push`, `pre-push` runs the shared pre-commit **pre-push** stage (pytest +
`scripts/run-container-structure-test.sh` from the #7 skeleton). Product Dockerfiles / CST YAML stay in consumers. Needs
Docker/tests when those hooks are active.

**Git LFS:** not part of the shared Devinfra image or hooks. Products that need LFS (e.g. sql-to-arc) install `git-lfs`
in a product-owned path that sync of the shared Dockerfile does not overwrite (product postCreate or a non-synced local
fragment) — see [`docs/devcontainer.md`](devcontainer.md).

Manual without the git hook:

```bash
uv run pre-commit run --all-files --hook-stage pre-push
```

## Manual runs (commit stage)

```bash
./scripts/quality-check.sh   # commit-stage, non-mutating only
./scripts/quality-fix.sh     # autofix hooks, then re-run quality-check
uv run pre-commit run --all-files   # full commit stage (includes autofixers)
```

On a **host** checkout, export `GITGUARDIAN_API_KEY` (and any other secrets hooks need) yourself — there is no
`~/.config/…` token helper outside the Dev Container.

## Container structure test parameters

`scripts/run-container-structure-test.sh` is **Bake-only** (no monolith `docker build -f`). Defaults:

| Input       | Default                                              | Override                 |
| ----------- | ---------------------------------------------------- | ------------------------ |
| Bake target | (required in product repos)                          | `CST_BAKE_TARGET` / `$1` |
| Bake file   | `docker-bake.hcl`                                    | `CST_BAKE_FILE`          |
| Image tag   | `app:structure-test`                                 | `CST_IMAGE_TAG` or `$2`  |
| Test config | `docker/container-structure-tests` (dir of `*.yaml`) | `CST_CONFIG` or `$3`     |

If `CST_BAKE_TARGET` is unset **and** this checkout has no product CST layout (no `docker/` at all, **or** `docker/`
without `docker/container-structure-tests/` — e.g. Devinfra with only `Dockerfile.product-app.base` + examples), the
script **skips** with a warning and exits 0 so pre-push can succeed. Product repos that ship
`docker/container-structure-tests/` must set `CST_BAKE_TARGET` (and a Bake file); wrong paths fail hard.

Optional Bake `*.args` values are taken from `versions.env` when set (`PYTHON_VERSION`, `UV_VERSION`, `ALPINE_VERSION`,
`ALPINE_MINOR`, `PIP_VERSION`, `PYINSTALLER_VERSION`). Those pins must not be restated as Dockerfile or Bake defaults.

Example (API-shaped product):

```bash
CST_BAKE_TARGET=api \
CST_IMAGE_TAG=fairagro-advanced-middleware-api:test \
CST_CONFIG=docker/container-structure-tests/api.yaml \
  ./scripts/run-container-structure-test.sh
```

## Notes

- Vendor skill trees under `.agents/skills/{gh,docker,hadolint,uv}/` (and `scan-secrets` if present) are excluded from
  tree-walking hooks — do not hand-edit those trees.
- This Devinfra repo has **no** `middleware/` packages; Python hooks scoped to `middleware/` apply after sync to a
  product repo.
