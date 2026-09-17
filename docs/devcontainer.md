# Dev Container

Open this repo with **Dev Containers: Reopen in Container** (VS Code or Cursor).

This image is the **shared product Dev Container toolchain** (issue #10): base pins in `versions.env`, fat tooling in
`.devcontainer/Dockerfile`, generic postCreate. Products adopt **verbatim** `.devcontainer/devcontainer.json` and
`.devcontainer/docker-compose.yml` from sync (#13,
[#65](https://github.com/fairagro/m4.2_middleware_devinfra/issues/65)) — do **not** hand-edit those blobs after sync.
Repo-specific container env (`MYPYPATH`, `CST_*`, …) belongs in optional product-owned `.devcontainer/product.env` (not
synced) and/or CI/hook env inputs.

OpenSpec **specs/changes** for product work stay in the product repos
([epic #1](https://github.com/fairagro/m4.2_middleware_devinfra/issues/1)); this image provides the OpenSpec CLI.

## Layout

| Path                                                | Purpose                                                                  |
| --------------------------------------------------- | ------------------------------------------------------------------------ |
| `.devcontainer/devcontainer.json`                   | **Verbatim** sync: Compose service, DinD, mounts, extensions, postCreate |
| `.devcontainer/docker-compose.yml`                  | **Verbatim** sync: build args from `versions.env`, bind `..:/workspace`  |
| `.devcontainer/product.env`                         | **Product-owned** (optional, not synced): `MYPYPATH`, `CST_*`, …         |
| `.devcontainer/Dockerfile`                          | Pinned shared tooling image                                              |
| [`.vscode/settings.json`](../.vscode/settings.json) | Shared workspace IDE settings (also apply on host clones)                |
| `versions.env`                                      | Single source of truth for tool versions                                 |
| `.devcontainer/.env`                                | Symlink → `../versions.env` (Compose build-arg substitution)             |

## Shared JSON + Compose contract (`/workspace`)

Fleet-wide in-container workspace path is **`/workspace`** (`workspaceFolder` and Compose bind). Window title and named
volumes use `${localWorkspaceFolderBasename}` so each opened folder stays distinct without product-specific JSON keys.

| Concern                       | Where                                                                                                                            |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Window / Dev Container `name` | Shared JSON: `${localWorkspaceFolderBasename}`                                                                                   |
| History / `gh` volumes        | Shared JSON: `${localWorkspaceFolderBasename}-bashhistory` / `-gh-config`                                                        |
| Workspace bind                | Shared Compose: `..:/workspace:cached`                                                                                           |
| `.venv/bin` + `scripts/bin`   | Shared JSON: `remoteEnv.PATH` = `/workspace/.venv/bin:/workspace/scripts/bin:…` (literal `/workspace`; not `${workspaceFolder}`) |
| Activated `.venv`             | Shared JSON: `remoteEnv.VIRTUAL_ENV=/workspace/.venv` (+ `VIRTUAL_ENV_PROMPT` = host folder basename)                            |
| Prompt repo name              | Shared JSON: `DEVCONTAINER_REPO_NAME` + synced `.devcontainer/starship.toml` (`STARSHIP_CONFIG`)                                 |
| `MYPYPATH`, `CST_*`, …        | Optional `.devcontainer/product.env` and/or CI inputs — **not** synced JSON/Compose                                              |

Starship’s leading segment is **`DEVCONTAINER_REPO_NAME`** (`${localWorkspaceFolderBasename}` via `remoteEnv`), not the
cwd basename (`workspace`). The synced [`.devcontainer/starship.toml`](../.devcontainer/starship.toml) is selected with
`STARSHIP_CONFIG`. The `.venv` is **activated** for IDE/agent shells by setting `VIRTUAL_ENV=/workspace/.venv` in
`remoteEnv` (PATH alone is not enough for tools/prompts that check that variable).

On sync, Prettier + markdownlint-cli2 (and their extensions) **replace or supplement** prior product markdown
format/lint setups. Prefer `signageos.signageos-vscode-sops` (Open VSX / Cursor) over `shipitsmarter.sops-edit`.

**Git LFS** is not part of the shared image or shared hook installer. Products that need it (e.g. sql-to-arc) own
install and hook overlays entirely in the product repo (independent of Devinfra). Shared `setup-git-hooks.sh` installs a
**dispatcher** (`.git/hooks/pre-push`) plus shared `.git/hooks/pre-push.d/50-quality`; it does not remove foreign
`pre-push.d` fragments or manage LFS `post-*` hooks. Products add numbered fragments under `pre-push.d/` (e.g.
`10-git-lfs` before `50-quality`). Shared postCreate does **not** hard-code `install-dev-hooks.sh` / `setup-git-lfs.sh`;
optional product work runs via **`scripts/devcontainer-post-create.d/*.sh`** (sorted, T-late, hard-fail if present and
non-executable or non-zero). Do **not** edit synced JSON `postCreate` for LFS.

## Tool versions

All toolchain pins live in repo-root [`versions.env`](../versions.env) (k8s tools, sops/age, jq/yq/xq, CST, Trivy,
Renovate, Node/`NPM_VERSION`/OpenSpec/Prettier/markdownlint, …). Distro packages (`jq`, `gnupg`, JRE, graphviz) come
from apt without a separate pin.

**Node vs npm:** `NODE_VERSION` installs the official Node tarball (which bundles some npm). The image then pins the
**npm CLI** with `npm install -g npm@${NPM_VERSION}` so the binary is Renovate-managed separately from Node. Ignore
npm’s self-update notice until Renovate bumps `NPM_VERSION` to current; once the pin matches the latest advertised
release, that notice should stop.

[`.python-version`](../.python-version) is kept aligned with `PYTHON_VERSION` (via `scripts/load-versions-env.sh`, also
run from postCreate).

**After changing pins:** edit `versions.env`, then **Dev Containers: Rebuild Container**.

```bash
gh --version
openspec --version
uv --version
node --version
npm --version
sops --version
trivy --version
renovate --version
```

## Tools in the image (shared)

| Area            | Tools                                                                                          |
| --------------- | ---------------------------------------------------------------------------------------------- |
| GitHub / Node   | `gh`, Node, pinned `npm`, OpenSpec, Prettier, markdownlint-cli2, Renovate                      |
| Python          | `uv` + pinned Python; quality CLIs via `uv sync` / pre-commit (ruff, …)                        |
| Query / lint    | `jq`, `yq`, `xq`, `yamlfmt`, `hadolint`                                                        |
| K8s             | `kubectl`, `helm`, `minikube`                                                                  |
| Secrets tooling | `sops`, `age`, `gpg` (ciphertext / `.sops.yaml` / `public_gpg_keys` **content** stay per repo) |
| Containers      | DinD feature, `container-structure-test` (`cst`), `trivy`                                      |
| Diagrams        | JRE + `graphviz` (PlantUML extension)                                                          |

Python quality tools (ruff, mypy, pylint, bandit, ggshield, pre-commit) are **project deps** via `uv`, not separate
image binaries — same pattern as product repos.

## Bashrc-free shell init (no `load-env.sh`)

Fleet shell convenience MUST NOT mutate `~/.bashrc`. Shared verbatim `devcontainer.json` already prepends
`/workspace/.venv/bin` and `/workspace/scripts/bin` via `remoteEnv.PATH` using the literal fleet workspace path, and
sets `VIRTUAL_ENV=/workspace/.venv` so the project venv is active without `source .venv/bin/activate`
([#58](https://github.com/fairagro/m4.2_middleware_devinfra/issues/58),
[#65](https://github.com/fairagro/m4.2_middleware_devinfra/issues/65),
[#143](https://github.com/fairagro/m4.2_middleware_devinfra/issues/143)). Do **not** use `${workspaceFolder}` in that
PATH string — Cursor agent shells leave it unexpanded, so `scripts/bin` wrappers never win over `/usr/bin/gh`. Repo name
in the prompt comes from `DEVCONTAINER_REPO_NAME` + synced `.devcontainer/starship.toml` (not from the `.venv` parent
path, which is always `workspace`).

| Need                            | Shared mechanism                                                                                                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.venv/bin` + `scripts/bin`     | `remoteEnv.PATH` + `VIRTUAL_ENV=/workspace/.venv` in synced `devcontainer.json`                                                                                                       |
| Prompt repo identity            | `DEVCONTAINER_REPO_NAME` + synced [`.devcontainer/starship.toml`](../.devcontainer/starship.toml) (`STARSHIP_CONFIG`)                                                                 |
| Short `kubectl` / `docker`      | Synced wrappers [`scripts/bin/k`](../scripts/bin/k) and [`scripts/bin/d`](../scripts/bin/d)                                                                                           |
| Bash completion for `k` / `d`   | Shared image files under `/usr/share/bash-completion/completions/` (rebuild after Dockerfile change)                                                                                  |
| Personal tokens                 | [`scripts/bin/gh`](../scripts/bin/gh) / [`git`](../scripts/bin/git) load `/commandhistory/tokens.env` on each invoke; `set-dev-tokens.sh` only **writes** the store (not process env) |
| `.env.integration.enc` → `.env` | Shared postCreate decrypt (writes the file; does **not** auto-`source` into every shell)                                                                                              |

Product-local `scripts/load-env.sh` and `setup-bashrc-load-env.sh` (or inline bashrc `source` lines) are **deprecated**.
After sync of postCreate + wrappers + JSON, drop them in product adopt follow-ups (tracked from #58 / #65). Optional
product deltas (`MYPYPATH`, CST bake target, …) belong in `.devcontainer/product.env` / CI — not a forked load-env blob.

## Markdown (format + lint)

| Tool                                                       | Role                                                                                     | VS Code / Cursor extension             |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------- |
| [Prettier](https://prettier.io)                            | Format (`printWidth` 120, `proseWrap: always`)                                           | `esbenp.prettier-vscode` (first-party) |
| [markdownlint](https://github.com/DavidAnson/markdownlint) | Structure lint; Prettier-compatible disables in `.markdownlint.json` (no `extends` path) | `davidanson.vscode-markdownlint`       |

Prettier and markdownlint-cli2 are installed **globally in the image**. Pins: `PRETTIER_VERSION`,
`MARKDOWNLINT_CLI2_VERSION` in `versions.env`; `package.json` mirrors them for host clones.

```bash
npm run format:md
npm run format:md:check
npm run lint:md
```

## Trivy / Renovate (local CLIs)

`trivy` and `renovate` are on `PATH` for local scans and config dry-runs. Shared **Renovate** config and GitHub workflow
live in this repo — see [`docs/renovate.md`](renovate.md) (token, dry-run, product migration). Reusable **Trivy** GitHub
Actions remain a separate CI concern.

## Bash history

History is stored in a Docker volume named `${localWorkspaceFolderBasename}-bashhistory` (mount
`HISTFILE=/commandhistory/.bash_history`). The image sets a large `HISTFILESIZE`, `histappend`, and `HISTIGNORE` so
Cursor/VS Code agent bootstrap lines (`set +/-o …`) do not flood the file and age out real commands.

**Note:** Changing volume `source=` names (e.g. from a fixed `middleware-devinfra-bashhistory` to basename-derived)
starts a **new** empty volume on rebuild; copy from the old volume if you need prior history.

One-time cleanup if an older volume is already polluted:

```bash
grep -vE '^(set |unset |shopt )' /commandhistory/.bash_history \
  > /tmp/bash_history.clean \
  && mv /tmp/bash_history.clean /commandhistory/.bash_history
```

## Host / credentials

Git credentials, SSH agent, and GPG agent are forwarded by the Dev Containers extension — no custom bind mounts
required.

Ensure on the **host**:

- `git config --global user.name` / `user.email` are set
- SSH agent running with keys loaded (`ssh-add`) if you use SSH remotes

### gh auth (HTTPS)

Prefer the personal-token helpers (see root README **Personal tokens**):

- Stored `GH_TOKEN` in `/commandhistory/tokens.env` (Linux Dev Container only) — **sole source** (process env does not
  override the store)
- Empty prompt skips until `source ./scripts/set-dev-tokens.sh` (that script **writes** the store; it does not export
  tokens into every agent/IDE process)
- `scripts/bin/gh` on `PATH` (after rebuild) applies the store then runs real `gh` — if `command -v gh` shows
  `/usr/bin/gh`, the `remoteEnv.PATH` contract is broken (see bashrc-free section / #143), not a missing store

Alternatively:

```bash
gh auth login
```

`gh` CLI login credentials (if used) live in Docker volume `${localWorkspaceFolderBasename}-gh-config` and survive
rebuilds.

## postCreateCommand

Runs `scripts/devcontainer-post-create.sh` once per create:

- fix `/commandhistory` and `~/.config/gh` permissions
- write `.python-version` from `versions.env` via `scripts/load-versions-env.sh`
- load stored tokens into the postCreate environment (no hang without TTY; no `~/.bashrc` patch)
- `uv sync --dev --all-packages` when `pyproject.toml` exists (dev dependency group + all uv workspace members; same
  flags as reusable code-quality CI). Stale `.venv` with a broken interpreter is removed first when detected.
- `pre-commit install --hook-type pre-commit`
- `./scripts/setup-git-hooks.sh` (dispatcher + `pre-push.d/50-quality`; does not manage Git LFS or hard-code product
  scripts)
- import `public_gpg_keys/*.asc` when present (skip if absent)
- optionally decrypt repo-root `.env.integration.enc` → `.env` when present (skip if `.env` already non-empty,
  ciphertext absent, or `sops`/keys unavailable; never fails create; does **not** patch bashrc to `source` `.env`)
- soft-fail install of recommended IDE extensions via Cursor/VS Code remote CLI (shared product set: Docker/Helm/
  Python/Ruff/Pylint/Mypy, PlantUML, Kubernetes Tools, signageos SOPS, Prettier, markdownlint, … — same list as
  `devcontainer.json` and synced `.vscode/extensions.json`)
- **T-late:** run `scripts/devcontainer-post-create.d/*` when present (sorted; hard-fail if not executable or non-zero;
  skip cleanly if the directory is absent/empty). Product-owned, **not** synced — e.g. a thin drop-in that runs
  `setup-git-lfs.sh`

`PATH` with `/workspace/.venv/bin` and `/workspace/scripts/bin` first, plus `VIRTUAL_ENV=/workspace/.venv`, comes from
`.devcontainer/devcontainer.json` (`remoteEnv`, literal `/workspace`) after rebuild — not from `~/.bashrc`.

Re-run anytime:

```bash
bash scripts/devcontainer-post-create.sh
```
