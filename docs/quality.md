# Shared quality tooling

Commit-stage and pre-push quality via [`pre-commit`](https://pre-commit.com). Canonical files live in this Devinfra repo
for sync into product consumers (`middleware/` package root — see [path conventions](conventions.md)).

## Script environments

Not every file under `scripts/` is Dev Container-only. Personal-token helpers are; quality runners are not.

| Script / tree                         | Environment            | Notes                                                                                                                                                    |
| ------------------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-check.sh` / `quality-fix.sh` | Host or Dev Container  | Needs `uv`. Commit-stage also runs `npm run lint:md` (Node/`npm`; host: `npm install`). On the host, set `GITGUARDIAN_API_KEY` for ggshield if required. |
| `run-container-structure-test.sh`     | Host or Dev Container  | Needs Docker + `container-structure-test`                                                                                                                |
| `run-quality-cli.sh`                  | Host or Dev Container  | `uv run --with-requirements scripts/quality-tools-pins.txt` for fleet quality CLIs                                                                       |
| `run-import-linter.sh`                | Host or Dev Container  | Product `.importlinter`; soft-skips without `middleware/`; uses `run-quality-cli.sh`                                                                     |
| `run-uv-audit.sh`                     | Host or Dev Container  | Needs `uv` + network to OSV; optional `.uv-audit-ignore`                                                                                                 |
| `setup-git-hooks.sh` / `git-hooks/`   | Host or Dev Container  | Dispatcher + `pre-push.d/50-quality`; no `git-lfs` required                                                                                              |
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

| Tool                    | IDE                                                 | Hooks             | CI  | Notes                                                                                     |
| ----------------------- | --------------------------------------------------- | ----------------- | --- | ----------------------------------------------------------------------------------------- |
| Ruff format/lint        | yes (`ruff.toml`)                                   | yes               | yes | Primary IDE Python lint/format                                                            |
| basedpyright / Pylance  | yes (`pyrightconfig.json`, `typeCheckingMode: off`) | —                 | —   | Language server only; type gate is mypy                                                   |
| Prettier / markdownlint | yes (Prettier formatter; markdownlint extension)    | yes               | yes | Shared `.markdownlint*` + Prettier; hooks + CI via `npm run format:md:check` / `lint:md`  |
| Mypy                    | yes (`mypy.ini` via `ms-python.mypy-type-checker`)  | yes (`mypy.ini`)  | yes | Same fragment; hooks/CI via `run-quality-cli.sh` (fleet pin); IDE may use project `.venv` |
| Pylint                  | yes (`.pylintrc` via `ms-python.pylint`)            | yes (`.pylintrc`) | yes | Same fragment; hooks/CI via `run-quality-cli.sh`; `--source-roots` stays CI/env           |
| Bandit                  | **hooks + CI only**                                 | yes (`.bandit`)   | yes | Named IDE exception; medium/high fail — see Bandit note below                             |
| Vulture                 | **hooks + CI only**                                 | — (CLI policy)    | yes | Named IDE exception; `--min-confidence 100`, no synced whitelist — see below              |
| import-linter           | **hooks + CI only**                                 | `.importlinter`   | yes | Named IDE exception; **product-owned** config — see below                                 |
| uv audit                | **hooks + CI only**                                 | — (CLI + overlay) | yes | Named IDE exception; frozen lockfile CVE gate; needs OSV network — see below              |
| pytest                  | IDE via `pyproject.toml` `testpaths`                | pre-push          | yes | Synced `pytestArgs` stay `[]` — do not hardcode roots in settings                         |

**Bandit severity (named exception):** `.bandit` has no fail-on-severity key. Hooks use Bandit’s `-ll` (report MEDIUM+
only). CI runs without `-ll`, logs all severities (JSON + wrapper), and still fails only on MEDIUM/HIGH — same fail bar
as hooks, matching [principles Code Quality](../openspec/principles.global.md#code-quality). Do not reintroduce a second
fail policy only on one surface.

**Fleet quality CLIs (hooks + reusable CI):** ggshield, ruff, mypy, pylint, bandit, vulture, and import-linter run via
[`scripts/quality-tools-pins.txt`](../scripts/quality-tools-pins.txt) (`bash scripts/run-quality-cli.sh` /
`scripts/quality-tools-pins.txt`). Pins live in that synced requirements file (Renovate `pip_requirements`) — **not** in
product `pyproject.toml`. Gates must not fail with `Failed to spawn` when a product omits those packages. Products
**MAY** still list the same tools as optional project deps for IDE extensions; pytest and other test-only deps stay
product-owned (`uv run pytest`).

**Vulture (named IDE exception):** unused-definition gate for `middleware/` (or reusable `python_package_root`). Hooks
and CI both run `bash scripts/run-quality-cli.sh vulture <root> --min-confidence 100` with **no** synced whitelist file.
False positives at that bar are fixed in product code (delete, use the symbol, or `# noqa`) — do **not** patch synced
`.pre-commit-config.yaml` or lower fleet confidence after sync. Ruff still owns unused **imports**; vulture owns unused
**definitions**.

**uv audit (named IDE exception):** primary **Python lockfile / env CVE gate** via `./scripts/run-uv-audit.sh`
(`uv audit --frozen`). Hooks and reusable code-quality share that runner. Fail on any finding except advisory IDs listed
in the product-owned overlay `.uv-audit-ignore` (one ID per line; sync `overlays` — never wiped). There is **no**
CRITICAL/HIGH-only filter (unlike Trivy on images). `uv audit` is still **preview** on the fleet uv pin — needs network
to OSV; escape hatch only: `SKIP=uv-audit`. See
[Lockfile CVEs vs Trivy vs malware check](#lockfile-cves-vs-trivy-vs-malware-check).

## Lockfile CVEs vs Trivy vs malware check

| Gate                   | Surface                  | When                                                     | Fail policy                                |
| ---------------------- | ------------------------ | -------------------------------------------------------- | ------------------------------------------ |
| **uv audit**           | `uv.lock` / project deps | Commit-stage + `reusable-code-quality` (no image needed) | Any non-ignored advisory / adverse status  |
| **Trivy**              | Container image / SBOM   | `reusable-check` Security Check (after image build)      | CRITICAL/HIGH                              |
| **`UV_MALWARE_CHECK`** | Install/sync             | `uv sync` in code-quality + Dev Container post-create    | Abort sync on known OSV **MAL** advisories |

Overlap on the same CVE across lock and image is OK — different layers. Do **not** disable Trivy because uv audit
exists. Malware check is **not** a CVE audit substitute (known malware only; still preview).

**import-linter (named IDE exception):** there is **no** synced import-linter **config** (no `.importlinter.global`) and
**no** config-merge logic. A thin synced [`scripts/run-import-linter.sh`](../scripts/run-import-linter.sh) only checks
paths and invokes the CLI. Every product repo **MUST** own a root **`.importlinter`** (sync `exclude` / `overlays` —
never copied or wiped by Devinfra sync) that includes the fleet-required settings below, plus product-specific `root_*`
and any `layers` / `forbidden` / `independence` contracts.

**Required in every product `.importlinter`:**

```ini
[importlinter]
exclude_type_checking_imports = True
# Regular package:
root_package = middleware
# Or PEP 420 portions (list every installed middleware.* portion; do NOT add a path-mutating
# middleware/__init__.py — Import policy):
# root_packages =
#     middleware.sql_to_arc
#     middleware.shared
#     middleware.api_client

[importlinter:contract:middleware-acyclic-siblings]
name = middleware sibling packages must be acyclic
type = acyclic_siblings
ancestors =
    middleware
```

Hooks and reusable CI run [`scripts/run-import-linter.sh`](../scripts/run-import-linter.sh) (thin wrapper: soft-skip
without `middleware/`, fail-closed without `.importlinter`, then `run-quality-cli.sh lint-imports …`). After a Devinfra
sync that drops a previously synced `.importlinter.global`, delete that orphan in the product and keep only
`.importlinter`.

**pydeps:** optional local visualization only — **not** a pre-commit or CI fail gate.

Import-policy rules **outside** import-linter (module-level imports, no relative imports, no `sys.path` mutation, no
lazy imports solely to break cycles) stay principles / other tools / `/code-review` judgment — see
[Import policy](../openspec/principles.global.md#import-policy).

## Files

| Path                                                | Role                                                                                                                         |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `.pre-commit-config.yaml`                           | Commit-stage + pre-push hooks — adopt **verbatim** after sync (see below)                                                    |
| `ruff.toml`                                         | Shared Ruff lint/format — **verbatim** sync (no product `extend` / ignore overlay)                                           |
| `mypy.ini`                                          | Shared Mypy strictness + fleet arctrl/fable `ignore_missing_imports` (path overlays via **env**)                             |
| `.pylintrc`                                         | Shared Pylint (`ignored-modules` for arctrl/fable; `extension-pkg-allow-list=lxml`; path overlays via CI / env)              |
| `pyrightconfig.json`                                | Shared basedpyright/Pylance (`venv`, `scripts/ai`, `typeCheckingMode: off`) — **verbatim**                                   |
| `scripts/quality-check.sh`                          | Run **commit-stage** hooks only (check)                                                                                      |
| `scripts/quality-fix.sh`                            | Run commit-stage **autofix** hooks only                                                                                      |
| `scripts/run-container-structure-test.sh`           | Templated Docker build + `container-structure-test`                                                                          |
| `scripts/run-import-linter.sh`                      | Thin import-linter runner (product `.importlinter`; see above)                                                               |
| `scripts/run-quality-cli.sh`                        | `uv run --with-requirements` wrapper for fleet quality CLIs                                                                  |
| `scripts/quality-tools-pins.txt`                    | Fleet pins for ggshield/ruff/mypy/pylint/bandit/vulture/import-linter (hooks + CI)                                           |
| `scripts/run-uv-audit.sh`                           | Frozen `uv audit` + optional product `.uv-audit-ignore` (hooks + CI)                                                         |
| `.importlinter`                                     | Product-owned import-linter config (fleet-required settings in this doc) — **not** synced from Devinfra                      |
| `scripts/setup-git-hooks.sh`                        | Install dispatcher + `pre-push.d/50-quality` from `scripts/git-hooks/`                                                       |
| `scripts/git-hooks/`                                | Version-controlled `pre-push` dispatcher + `pre-push.d/`                                                                     |
| `.bandit`                                           | Bandit config (`bandit -c .bandit`)                                                                                          |
| `.markdownlint.json` (+ ignore / cli2)              | Markdownlint (also used by the markdownlint hook)                                                                            |
| `package.json` / `package-lock.json`                | Shared npm scripts + pins for Prettier/markdownlint (`prettier-md` + `markdownlint` hooks + reusable CI) — **verbatim** sync |
| [`.vscode/settings.json`](../.vscode/settings.json) | Shared IDE baseline (interpreter, Ruff, Mypy, Pylint, empty `pytestArgs`, Prettier) — adopt **verbatim**                     |

**Local artifact excludes:** repo-root `dist/` (PyInstaller onedir, etc.) is gitignored and already skipped by Ruff /
Mypy / Pylint / Bandit. Markdown/Node tools must match: synced `.markdownlint-cli2.jsonc`, `.markdownlintignore`, and
`.prettierignore` ignore `dist/**` (same class as `.venv/` / `node_modules/`). IDE analysis excludes `**/dist` in
`pyrightconfig.json` and `.vscode/settings.json`. Do not hand-edit those lists in product checkouts after sync.

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
- Commit-stage `prettier-md` (`npm run format:md:check`) and `markdownlint` (`npm run lint:md`) share the same `files` /
  `exclude` class for `*.md` / `*.mdc` (parity with reusable CI). Escape hatch only: `SKIP=prettier-md` or
  `SKIP=markdownlint` (same class as other Node markdown hooks — not the normal workflow).
- CST bake target / image tag come from env (`CST_BAKE_*`), not from a product-hardcoded hook entry.
- pytest uses product `pyproject.toml` discovery; the shared pre-push hook runs
  `uv run pytest -m "not system_external and not system_local"` (see [Pre-push pytest scope](#pre-push-pytest-scope)).

Path overlays for Mypy/Pylint belong **outside** the synced YAML. Prefer a single product-owned
[`.devcontainer/product.env`](devcontainer.md) with:

```bash
# .devcontainer/product.env (not synced)
MYPYPATH=middleware/foo/src:middleware/bar/src
PYLINT_SOURCE_ROOTS=middleware/foo/tests/unit,middleware/bar/tests/unit
```

Reusable CI loads those keys when `mypy_path` / `pylint_source_roots` inputs are empty ([`docs/ci.md`](ci.md)). Synced
[`scripts/run-quality-cli.sh`](../scripts/run-quality-cli.sh) applies the same file on each invoke when the vars are
unset (so edits apply without a Dev Container rebuild). Non-empty process env or workflow inputs win. Do **not** put
path lists in synced `mypy.ini` / `.pre-commit-config.yaml`. Adopter follow-up:
[harvester#299](https://github.com/fairagro/m4.2_middleware_harvester/issues/299).

**Pylint `--source-roots`:** when `PYLINT_SOURCE_ROOTS` is set (file or env), `run-quality-cli.sh pylint` injects
`--source-roots=…` unless the caller already passed that flag. Do not patch synced `.pre-commit-config.yaml` to
hard-code product roots.

## Shared Python quality fragments (B2)

Product repos historically kept large `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]` blocks in root `pyproject.toml`.
Canonical copies live here as **fragment files** so sync (#13) can overwrite them without replacing product `[project]`
/ uv workspace sections.

| Sync into products   | Keep product-local                                                                                                                                                                                                                                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ruff.toml`          | Root `pyproject.toml` `[project]`, `[tool.uv.*]`, deps (no product Ruff overlay)                                                                                                                                                                                         |
| `mypy.ini`           | Fleet `arctrl` / `fable_library` `ignore_missing_imports`; path overlays via **env** (`MYPYPATH`)                                                                                                                                                                        |
| `.pylintrc`          | Fleet `ignored-modules` for arctrl/fable; path overlays via CI / env (`pylint_source_roots`)                                                                                                                                                                             |
| `pyrightconfig.json` | `typeCheckingMode: off` (LS = mypy); no middleware paths; no `stubPath`                                                                                                                                                                                                  |
| `.bandit`            | pytest markers / coverage: products keep local registration until the **planned** pytest-plugin SoT ships ([#123](https://github.com/fairagro/m4.2_middleware_devinfra/issues/123); design `fleet-pytest-markers-plugin-design`); coverage fragment is a later follow-up |

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

**Not** in the product quality sync set as a root-workspace member: `scripts/ai/pyproject.toml` is still the Devinfra
`m42-ai-gh` package manifest — but products **do** sync `scripts/ai/**` including `scripts/ai/uv.lock` for
`--project scripts/ai` invocations (see [`scripts/ai/README.md`](../scripts/ai/README.md)).

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
wires `ms-python.mypy-type-checker` / `ms-python.pylint` to the same `.venv` and `mypy.ini` / `.pylintrc` (no product
path overlays in settings — `MYPYPATH` / `pylint_source_roots` stay env/CI), and sets Prettier as default formatter for
Markdown/JSON/YAML. Helm chart templates under `helmchart/**/templates/` and `helm/**/templates/` use language mode
`helm` via Kubernetes Tools (`files.associations`); missing-kubeconfig toasts are suppressed
(`vs-kubernetes.suppress-kubeconfig-not-found-alerts`) because Dev Containers often have no cluster config —
kubectl-not-found alerts stay enabled.

**pytest discovery:** keep `"python.testing.pytestArgs": []` (or omit the key). Non-empty args become CLI paths and
**override** each checkout’s `[tool.pytest.ini_options] testpaths` (see
[vscode-python#23714](https://github.com/microsoft/vscode-python/issues/23714)). Configure test roots only in that
repo’s `pyproject.toml` (Devinfra: `scripts/ai/tests`; products: their `middleware/…/tests`).

**Untyped fleet deps (arctrl / fable_library):** silenced in synced tool fragments — [`mypy.ini`](../mypy.ini)
(`ignore_missing_imports`), [`.pylintrc`](../.pylintrc) (`ignored-modules`), and [`ruff.toml`](../ruff.toml)
(`known-third-party` for isort; Ruff has no third-party missing-import gate). Prefer those configs over call-site
`# type: ignore[import-untyped]` for arctrl/fable. Do **not** ship a Devinfra `stubs/` tree.

**Analysis (basedpyright / Pylance):** use synced [`pyrightconfig.json`](../pyrightconfig.json) **verbatim** — root
`.venv`, `extraPaths` only for `scripts/ai/src`, and `typeCheckingMode: "off"` so the language server stays for IDE
navigation while **mypy** owns type diagnostics (IDE extension + hooks + CI). Do **not** add product `middleware/` paths
— editable `uv` installs resolve them. Do **not** patch `python.analysis.extraPaths` / Cursor Pyright equivalents into
synced `.vscode/settings.json` after sync for product overlays ([`docs/sync.md`](sync.md)).

**Mypy / Pylint IDE:** synced settings point the recommended extensions at `.venv` and the shared fragments. IDE
diagnostics may run on open files while hooks/CI scan `middleware/` — same config and the same finding for the same
file; hooks remain the commit gate. Do **not** invent a second mypy/pylint rule set in product-local IDE settings.

**Bandit** stays **hooks + CI only** in the shared baseline (no Bandit IDE extension settings) — see
[Environment parity](#environment-parity-ide-hooks-ci).

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

Installs `.git/hooks/pre-push` (dispatcher) and `.git/hooks/pre-push.d/50-quality` from `scripts/git-hooks/`. Does
**not** require, install, or manage Git LFS; does **not** delete other hooks or foreign `pre-push.d` fragments.
Idempotent re-runs refresh only the shared-owned paths. Invoked from Dev Container postCreate, or once after clone.
Shared postCreate does **not** hard-code product scripts such as `install-dev-hooks.sh`; optional product work uses
`scripts/devcontainer-post-create.d/` (see [`docs/devcontainer.md`](devcontainer.md)).

On `git push`, the dispatcher runs `pre-push.d/*` in lexicographic order (e.g. product `10-git-lfs` then shared
`50-quality`). The quality fragment runs the shared pre-commit **pre-push** stage (pytest +
`scripts/run-container-structure-test.sh` from the #7 skeleton). Product Dockerfiles / CST YAML stay in consumers. Needs
Docker/tests when those hooks are active. Products that need extra pre-push steps MUST drop numbered executables into
`.git/hooks/pre-push.d/` via a product installer and MUST NOT replace the shared dispatcher wholesale.

### Pre-push pytest scope

Synced pre-push pytest excludes heavy system suites by default:

```text
-m "not system_external and not system_local"
```

Products must register those markers in local `pyproject.toml` (or equivalent) so `--strict-markers` stays valid until
the planned fleet SoT lands. **Locked design** ([#123](https://github.com/fairagro/m4.2_middleware_devinfra/issues/123),
OpenSpec change `fleet-pytest-markers-plugin-design`): a Devinfra **pytest plugin** will register the shared marker set
(product `testpaths` / `pythonpath` stay local); a shared **coverage** fragment is deferred as a separate follow-up. Do
**not** hand-copy marker strings into Devinfra sync blobs as a permanent product fork, and do **not** treat this docs
note as “the plugin already ships.”

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
entirely in the product repo (including optional `pre-push.d` fragments and flat `post-*` hooks); restore after
clone/rebuild via `scripts/devcontainer-post-create.d/` — see [`docs/devcontainer.md`](devcontainer.md). Do **not** edit
synced Dev Container JSON `postCreate` for LFS.

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
