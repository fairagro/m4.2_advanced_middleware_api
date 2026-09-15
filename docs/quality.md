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

| Environment   | How it runs                                                                                                                               | Config source                                |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| **IDE**       | [`.vscode/settings.json`](../.vscode/settings.json) + recommended extensions                                                              | Same fragment / config files as hooks and CI |
| **Hooks**     | pre-commit (commit) / pre-push stage; `./scripts/quality-check.sh`                                                                        | `.pre-commit-config.yaml` → shared configs   |
| **GitHub CI** | [`reusable-code-quality.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-code-quality.yml) | Same shared configs                          |

**Matching results** means the same pass/fail gate and the same policy findings (rule id + location). Log formatting may
differ (IDE diagnostics vs CLI). **Bandit exception:** the fail bar is the same (MEDIUM/HIGH fail; LOW never fails), but
CI may **log** LOW findings while hooks suppress them with `-ll` — see the Bandit note below.

**Minimal CLI / IDE args:** pass only the config-file path (when the tool does not auto-discover it), target paths, and
documented path overlays via **environment / CI inputs** (`MYPYPATH`, reusable-workflow `pylint_source_roots`). Do not
restate line length, rule selects, ignore lists, or similar policy on the command line when the shared config file
already defines them. Do not patch synced `.pre-commit-config.yaml` to carry those overlays. After syncing `.pylintrc`,
products may drop a duplicate `--extension-pkg-allow-list=lxml` CLI flag — that allow-list lives in the rcfile.

| Tool                    | IDE                                              | Hooks             | CI  | Notes                                                                            |
| ----------------------- | ------------------------------------------------ | ----------------- | --- | -------------------------------------------------------------------------------- |
| Ruff format/lint        | yes (`ruff.toml`)                                | yes               | yes | Primary IDE Python lint/format                                                   |
| basedpyright / Pylance  | yes (`pyrightconfig.json`)                       | —                 | —   | Synced analysis fragment; product stubs via `stubPath`                           |
| Prettier / markdownlint | yes (Prettier formatter; markdownlint extension) | yes               | yes | Shared `.markdownlint*` + Prettier; CI via `npm run format:md:check` / `lint:md` |
| Mypy                    | **hooks + CI only**                              | yes (`mypy.ini`)  | yes | No shared IDE mypy settings — do not add a second config                         |
| Pylint                  | **hooks + CI only**                              | yes (`.pylintrc`) | yes | Same as Mypy                                                                     |
| Bandit                  | **hooks + CI only**                              | yes (`.bandit`)   | yes | Medium/high fail; see Bandit note below                                          |
| pytest                  | IDE via `pyproject.toml` `testpaths`             | pre-push          | yes | Synced `pytestArgs` stay `[]` — do not hardcode roots in settings                |

**Bandit severity (named exception):** `.bandit` has no fail-on-severity key. Hooks use Bandit’s `-ll` (report MEDIUM+
only). CI runs without `-ll`, logs all severities (JSON + wrapper), and still fails only on MEDIUM/HIGH — same fail bar
as hooks, matching [principles Code Quality](../openspec/principles.global.md#code-quality). Do not reintroduce a second
fail policy only on one surface.

## Files

| Path                                                | Role                                                                                                                                         |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `.pre-commit-config.yaml`                           | Commit-stage + pre-push hooks — adopt **verbatim** after sync (see below)                                                                    |
| `ruff.toml`                                         | Shared Ruff lint/format — **verbatim** sync (no product `extend` / ignore overlay)                                                           |
| `mypy.ini`                                          | Shared Mypy strictness (path overlays via **env**, not by editing this file)                                                                 |
| `.pylintrc`                                         | Shared Pylint (path overlays via CI / env; `extension-pkg-allow-list=lxml` for I1101)                                                        |
| `pyrightconfig.json`                                | Shared basedpyright/Pylance (`venv`, `stubPath: stubs`, `scripts/ai` only) — **verbatim**                                                    |
| `stubs/arctrl/`, `stubs/fable_library/`             | Shared incomplete stubs for untyped arctrl/fable — **verbatim** sync ([#67](https://github.com/fairagro/m4.2_middleware_devinfra/issues/67)) |
| `stubs/README.md`                                   | Fleet vs product-local vs one-off stub/silence contract                                                                                      |
| `scripts/quality-check.sh`                          | Run **commit-stage** hooks only (check)                                                                                                      |
| `scripts/quality-fix.sh`                            | Run commit-stage **autofix** hooks only                                                                                                      |
| `scripts/run-container-structure-test.sh`           | Templated Docker build + `container-structure-test`                                                                                          |
| `scripts/setup-git-hooks.sh`                        | Install project `pre-push` from `scripts/git-hooks/`                                                                                         |
| `scripts/git-hooks/`                                | Version-controlled `pre-push` (pre-commit pre-push stage)                                                                                    |
| `.bandit`                                           | Bandit config (`bandit -c .bandit`)                                                                                                          |
| `.markdownlint.json` (+ ignore / cli2)              | Markdownlint (also used by the markdownlint hook)                                                                                            |
| `package.json` / `package-lock.json`                | Shared npm scripts + pins for Prettier/markdownlint (hooks + reusable CI) — **verbatim** sync                                                |
| [`.vscode/settings.json`](../.vscode/settings.json) | Shared IDE baseline (interpreter, Ruff, empty `pytestArgs`, Prettier) — adopt **verbatim**                                                   |

## Shared pre-commit config (verbatim sync)

[`.pre-commit-config.yaml`](../.pre-commit-config.yaml) is on the sync allowlist
([`docs/synced-paths.yaml`](synced-paths.yaml)). Products MUST adopt it **verbatim**.

Do **not** hand-edit that file in a product checkout after sync (no product-only `entry` / `args` / `exclude` / `env`
patches on the synced blob). Fleet rule ([#63](https://github.com/fairagro/m4.2_middleware_devinfra/issues/63),
[#57](https://github.com/fairagro/m4.2_middleware_devinfra/issues/57)): either Devinfra generalizes the need, or the
exception is a documented product-local surface that sync does **not** overwrite — never “re-patch after every sync”.

Examples already in the shared skeleton:

- `check-yaml` excludes Go-templated Helm under `helm/**/templates/` and `helmchart/**/templates/` (and vendor skill
  trees) — safe when those paths are absent.
- CST bake target / image tag come from env (`CST_BAKE_*`), not from a product-hardcoded hook entry.
- pytest uses product `pyproject.toml` discovery; the shared pre-push hook runs
  `uv run pytest -m "not system_external and not system_local"` (see [Pre-push pytest scope](#pre-push-pytest-scope)).

Path overlays for Mypy/Pylint belong **outside** the synced YAML (optional `.devcontainer/product.env`, process env, and
reusable CI inputs such as `mypy_path` and `pylint_source_roots` in [`docs/ci.md`](ci.md) — not synced JSON `remoteEnv`
for `MYPYPATH`). Prefer generalizing into Devinfra when every product needs the same roots.

## Shared Python quality fragments (B2)

Product repos historically kept large `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` blocks in root `pyproject.toml`.
Canonical copies live here as **fragment files** so sync (#13) can overwrite them without replacing product `[project]`
/ uv workspace sections.

| Sync into products                          | Keep product-local                                                                                               |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `ruff.toml`                                 | Root `pyproject.toml` `[project]`, `[tool.uv.*]`, deps (no product Ruff overlay)                                 |
| `mypy.ini`                                  | Import-path overlays via **env** (e.g. `MYPYPATH` in CI/`product.env`), not `pyproject`                          |
| `.pylintrc`                                 | Import-path overlays via CI input / env-driven invocation (`pylint_source_roots`)                                |
| `pyrightconfig.json`                        | Product third-party stubs under `stubs/` (`stubPath`); no middleware `extraPaths`                                |
| `stubs/arctrl/**`, `stubs/fable_library/**` | Put `stubs` on `MYPYPATH`; no `[mypy-arctrl*]` in synced `mypy.ini`                                              |
| `.bandit`                                   | pytest / coverage tool tables ([#123](https://github.com/fairagro/m4.2_middleware_devinfra/issues/123) deferred) |

Shared hooks and reusable CI invoke `mypy --config-file mypy.ini` and `pylint --rcfile .pylintrc`. Those flags mean
product `[tool.mypy]` / `[tool.pylint.*]` in `pyproject.toml` are **ignored**. Do **not** put path overlays into the
synced fragments or into synced `.pre-commit-config.yaml` — sync (#13) overwrites both. Use product CI inputs / process
env (examples in `mypy.ini` / `.pylintrc` headers and [`docs/ci.md`](ci.md)). If a product needs a hook change that
cannot be expressed that way, open a Devinfra issue to generalize — do not leave a permanent post-sync YAML patch.

**lxml / I1101:** `lxml` is a C extension. Keep the real type (`lxml.etree._Element`); do not silence
`c-extension-no-member` (I1101) with `Any` or an `Any`-shaped alias. Shared `.pylintrc` sets
`extension-pkg-allow-list=lxml` so IDE Pylint (rcfile only) and `--rcfile` invocations see members. Do not disable I1101
globally ([Type Safety](../openspec/principles.global.md#type-safety)). Product hooks/CI that still pass
`--extension-pkg-allow-list=lxml` can drop that flag after this fragment is synced.

**Not** in the product quality sync set: `scripts/ai/pyproject.toml` (Devinfra `m42-ai-gh` package manifest only).

After sync, products should **remove** duplicated `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` from root
`pyproject.toml` so the fragments are the single tool config. First adoption smoke is expected via sync / product PRs
([#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)), not in the Devinfra MVP PR
([#28](https://github.com/fairagro/m4.2_middleware_devinfra/issues/28)).

Shared **app Dockerfile** base + product-local last stage lives in this repo as
[`docker/Dockerfile.product-app.base`](../docker/Dockerfile.product-app.base) with Bake examples under
[`docker/examples/`](https://github.com/fairagro/m4.2_middleware_devinfra/tree/main/docker/examples/) (Devinfra-only —
not synced). Sync the **base** into products; keep the last stage and `docker-bake.hcl` product-local. Reusable
build/release are **Bake-only** (no monolith Dockerfile) — see
[`docs/ci.md`](ci.md#product-app-images-bake-base--last-stage). Adoption:
[#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13) / product Wave C (issue
[#36](https://github.com/fairagro/m4.2_middleware_devinfra/issues/36)).

## IDE (workspace settings)

[`.vscode/settings.json`](../.vscode/settings.json) is part of the shared Devinfra surface (host + Dev Container) and is
on the sync allowlist. Adopt it **verbatim** — workspace `settings.json` has **no** `extends` / merge, so product keys
cannot layer onto the synced blob without post-sync hand-edits ([`docs/sync.md`](sync.md)). Synced
[`.vscode/extensions.json`](../.vscode/extensions.json) recommendations MUST match the Dev Container extension list
(including `ms-kubernetes-tools.vscode-kubernetes-tools`).

It points the Python extension at the root `.venv` from `uv sync`, configures Ruff via `ruff.toml` like pre-commit/CI,
and sets Prettier as default formatter for Markdown/JSON/YAML. Helm chart templates under `helmchart/**/templates/` and
`helm/**/templates/` use language mode `helm` via Kubernetes Tools (`files.associations`); missing-kubeconfig toasts are
suppressed (`vs-kubernetes.suppress-kubeconfig-not-found-alerts`) because Dev Containers often have no cluster config —
kubectl-not-found alerts stay enabled.

**pytest discovery:** keep `"python.testing.pytestArgs": []` (or omit the key). Non-empty args become CLI paths and
**override** each checkout’s `[tool.pytest.ini_options] testpaths` (see
[vscode-python#23714](https://github.com/microsoft/vscode-python/issues/23714)). Configure test roots only in that
repo’s `pyproject.toml` (Devinfra: `scripts/ai/tests`; products: their `middleware/…/tests`).

**Shared stubs (arctrl / fable_library):** sync [`stubs/arctrl/`](../stubs/arctrl/) and
[`stubs/fable_library/`](../stubs/fable_library/) (see [`stubs/README.md`](../stubs/README.md)). Products MUST put
`stubs` on `MYPYPATH` for hooks/CI. Do **not** add `[mypy-arctrl*]` / fable module overrides to synced `mypy.ini`, and
drop `# type: ignore[import-untyped]` on those imports after sync. Product-local stubs (e.g. owslib/rdflib) may coexist
under `stubs/` without being synced from Devinfra.

**Analysis (basedpyright / Pylance):** use synced [`pyrightconfig.json`](../pyrightconfig.json) **verbatim** — root
`.venv`, `stubPath: stubs` (shared arctrl/fable stubs + any product-local stub dirs), and `extraPaths` only for
`scripts/ai/src`. Do **not** add product `middleware/` (or other package) paths to that file — editable `uv` installs
resolve them. Do **not** patch `python.analysis.extraPaths` / Cursor Pyright equivalents into synced
`.vscode/settings.json` after sync for product overlays ([`docs/sync.md`](sync.md)).

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

Copies `scripts/git-hooks/pre-push` into `.git/hooks/`. Does **not** require, install, or manage Git LFS (does not
delete other hooks). Invoked from Dev Container postCreate, or once after clone. Shared postCreate does **not** call
product scripts such as `install-dev-hooks.sh`.

On `git push`, `pre-push` runs the shared pre-commit **pre-push** stage (pytest +
`scripts/run-container-structure-test.sh` from the #7 skeleton). Product Dockerfiles / CST YAML stay in consumers. Needs
Docker/tests when those hooks are active.

### Pre-push pytest scope

Synced pre-push pytest excludes heavy system suites by default:

```text
-m "not system_external and not system_local"
```

Products must register those markers in local `pyproject.toml` (or equivalent) so `--strict-markers` stays valid. A
shared pytest-plugin / coverage-fragment SoT is deferred
([#123](https://github.com/fairagro/m4.2_middleware_devinfra/issues/123)) — do **not** hand-copy marker strings into
Devinfra sync blobs as a permanent product fork.

The remaining suite can still take several minutes. The hook prints a short notice before pytest runs.
`SKIP=pytest git push` is an **escape hatch only**, not the normal workflow.

| Where                        | Scope                                                                  |
| ---------------------------- | ---------------------------------------------------------------------- |
| Synced pre-push              | Excludes `system_external` / `system_local`                            |
| Reusable / product CI        | Broader suite — does **not** inherit the pre-push `-m` filter          |
| Intentional local `system_*` | Explicit `uv run pytest -m system_external` (or `system_local`) / path |

Do **not** fork synced `.pre-commit-config.yaml` to restore system tests on every push — run them intentionally or rely
on CI ([`docs/ci.md`](ci.md)).

**Git LFS:** not part of the shared Devinfra image or hook installer. Products that need LFS own install and overlays
entirely in the product repo; re-apply product-side after clone/rebuild when needed — see
[`docs/devcontainer.md`](devcontainer.md). Do **not** edit synced Dev Container JSON `postCreate` for LFS.

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
