# Dev Container

Open this repo with **Dev Containers: Reopen in Container** (VS Code or Cursor).

This image is the **shared product Dev Container toolchain** (issue #10): base pins in `versions.env`, fat tooling in
`.devcontainer/Dockerfile`, generic postCreate. Product repos keep a thin `devcontainer.json` overlay (`name`,
`workspaceFolder`, distinct volume `source=` names; optional extra extensions) and sync Dockerfile / compose /
`versions.env` / scripts from here (#13).

OpenSpec **specs/changes** for product work stay in the product repos
([epic #1](https://github.com/fairagro/m4.2_middleware_devinfra/issues/1)); this image provides the OpenSpec CLI.

## Layout

| Path                                                | Purpose                                                      |
| --------------------------------------------------- | ------------------------------------------------------------ |
| `.devcontainer/devcontainer.json`                   | Compose service, DinD, mounts, extensions, postCreate        |
| `.devcontainer/docker-compose.yml`                  | Build args from `versions.env` via `.env` symlink            |
| `.devcontainer/Dockerfile`                          | Pinned shared tooling image                                  |
| [`.vscode/settings.json`](../.vscode/settings.json) | Shared workspace IDE settings (also apply on host clones)    |
| `versions.env`                                      | Single source of truth for tool versions                     |
| `.devcontainer/.env`                                | Symlink → `../versions.env` (Compose build-arg substitution) |

## Tool versions

All toolchain pins live in repo-root [`versions.env`](../versions.env) (k8s tools, sops/age, jq/yq/xq, CST, Trivy,
Renovate, Node/OpenSpec/Prettier/markdownlint, …). Distro packages (`jq`, `gnupg`, JRE, graphviz) come from apt without
a separate pin.

[`.python-version`](../.python-version) is kept aligned with `PYTHON_VERSION` (via `scripts/load-versions-env.sh`, also
run from postCreate).

**After changing pins:** edit `versions.env`, then **Dev Containers: Rebuild Container**.

```bash
gh --version
openspec --version
uv --version
node --version
sops --version
trivy --version
renovate --version
```

## Tools in the image (shared)

| Area            | Tools                                                                                          |
| --------------- | ---------------------------------------------------------------------------------------------- |
| GitHub / Node   | `gh`, Node, OpenSpec, Prettier, markdownlint-cli2, Renovate                                    |
| Python          | `uv` + pinned Python; quality CLIs via `uv sync` / pre-commit (ruff, …)                        |
| Query / lint    | `jq`, `yq`, `xq`, `yamlfmt`, `hadolint`                                                        |
| K8s             | `kubectl`, `helm`, `minikube`                                                                  |
| Secrets tooling | `sops`, `age`, `gpg` (ciphertext / `.sops.yaml` / `public_gpg_keys` **content** stay per repo) |
| Containers      | DinD feature, `container-structure-test` (`cst`), `trivy`                                      |
| Diagrams        | JRE + `graphviz` (PlantUML extension)                                                          |

Python quality tools (ruff, mypy, pylint, bandit, ggshield, pre-commit) are **project deps** via `uv`, not separate
image binaries — same pattern as product repos.

## Consumer overlays

Product `devcontainer.json` should own at least:

- `name`
- `workspaceFolder` (must match that product’s compose bind path)
- distinct Docker volume `source=` names (do not reuse another product’s volume names)

Shared fragments must **not** hardcode another product’s folder or volume names. On sync, Prettier + markdownlint-cli2
(and their extensions) **replace or supplement** prior product markdown format/lint setups. Prefer
`signageos.signageos-vscode-sops` (Open VSX / Cursor) over `shipitsmarter.sops-edit`.

**Git LFS** is not part of the shared image. Products that need it (e.g. sql-to-arc) install `git-lfs` in a
**product-owned** path that sync of the shared Dockerfile does not overwrite (e.g. product postCreate snippet or a
non-synced local fragment).

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

History is stored in Docker volume `middleware-devinfra-bashhistory` (`HISTFILE=/commandhistory/.bash_history`). The
image sets a large `HISTFILESIZE`, `histappend`, and `HISTIGNORE` so Cursor/VS Code agent bootstrap lines (`set +/-o …`)
do not flood the file and age out real commands.

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

- Stored `GH_TOKEN` in `/commandhistory/tokens.env` (Linux Dev Container only)
- Empty prompt skips until `source ./scripts/set-dev-tokens.sh`
- `scripts/bin/gh` on `PATH` (after rebuild) loads tokens then runs real `gh`

Alternatively:

```bash
gh auth login
```

`gh` CLI login credentials (if used) live in Docker volume `middleware-devinfra-gh-config` and survive rebuilds.

## postCreateCommand

Runs `scripts/devcontainer-post-create.sh` once per create:

- fix `/commandhistory` and `~/.config/gh` permissions
- write `.python-version` from `versions.env` via `scripts/load-versions-env.sh`
- load stored tokens into the postCreate environment (no hang without TTY; no `~/.bashrc` patch)
- `uv sync` when `pyproject.toml` exists
- `pre-commit install --hook-type pre-commit`
- `./scripts/setup-git-hooks.sh` (project pre-push quality hook; no Git LFS)
- import `public_gpg_keys/*.asc` when present (skip if absent)
- soft-fail install of recommended IDE extensions via Cursor/VS Code remote CLI (shared product set: Docker/Helm/
  Python/Ruff/Pylint/Mypy, PlantUML, signageos SOPS, Prettier, markdownlint, … — same list as `devcontainer.json`)

`PATH` with `scripts/bin` first comes from `.devcontainer/devcontainer.json` (`remoteEnv`) after rebuild.

Re-run anytime:

```bash
bash scripts/devcontainer-post-create.sh
```
