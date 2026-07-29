# Dev Container

Single shared definition for **VS Code** and **Cursor** (both support Dev Containers natively).

Open the repo and use **Reopen in Container** / **Dev Containers: Reopen in Container**.

## Layout

| Path | Purpose |
| ---- | ------- |
| `devcontainer.json` | Shared container config (DinD, mounts, extensions, postCreate) |
| `Dockerfile` | Pinned tooling image (Python via uv, Node.js, OpenSpec, sops, kubectl, …) |

## Node.js and OpenSpec

The image pins **Node.js 20.x** (official binary under `/usr/local`) and installs
the [`@fission-ai/openspec`](https://www.npmjs.com/package/@fission-ai/openspec)
CLI globally into `/usr/local` (`openspec` on `PATH`).

After changing `NODE_VERSION` or `OPENSPEC_VERSION` in the Dockerfile, rebuild
the Dev Container (**Dev Containers: Rebuild Container**).

Project setup (once per clone, after rebuild):

```bash
openspec --version
# If openspec/ is already in the repo:
openspec update
```

## Host bind mounts

| Mount | Source | Platforms |
| ----- | ------ | --------- |
| Shell history | named volume `middleware-api-bashhistory` | all |

Host `~/.gitconfig` is copied/synced by the Dev Containers tooling (no manual mount).

## GPG / SOPS

Dev Containers forward the host **gpg-agent** automatically (no custom mounts or setup
script). Private-key operations such as `sops -d` use the host secret key via that agent.

postCreate imports project **public** keys from `public_gpg_keys/` via
`scripts/import-public-gpg-keys.sh` (encrypt / recipient checks).

If decrypt still fails, unlock the agent on the host (`gpg -K` / enter passphrase) and
ensure the IDE's GPG agent forwarding is enabled. As a fallback, decrypt on the host:

```bash
sops -d .env.integration.enc > .env
```

`scripts/load-env.sh` skips SOPS decryption when `.env` already exists.

## One-time setup (postCreateCommand)

- `uv sync --dev --all-packages`
- `scripts/install-dev-hooks.sh` (pre-commit + Git LFS hooks)
- `scripts/import-public-gpg-keys.sh`
- `scripts/install-ruff-extension.sh` (Cursor/VS Code remote CLI)

`scripts/load-env.sh` is sourced from `~/.bashrc` (PATH, aliases, SOPS when needed).

## SOPS in the editor

`signageos.signageos-vscode-sops` is installed (`@signageos/vscode-sops` on Open VSX).
The `sops` CLI is on `PATH` in the image.

## Ruff extension

`charliermarsh.ruff` is **not** listed under `customizations.vscode.extensions` because Cursor's
marketplace UI can hang on install (dependency cycle with Python/Pylance; see
[astral-sh/ruff-vscode#943](https://github.com/astral-sh/ruff-vscode/issues/943)).

postCreate runs `scripts/install-ruff-extension.sh`, which installs Ruff via the Cursor or
VS Code remote CLI. Fallback:

```bash
uv run ruff check middleware/
uv run ruff format middleware/
# or
./scripts/quality-fix.sh
```

## Local clone (no Dev Container)

```bash
./scripts/install-dev-hooks.sh
./scripts/import-public-gpg-keys.sh
```
