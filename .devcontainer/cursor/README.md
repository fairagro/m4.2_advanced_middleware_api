# Cursor devcontainer (DevPod)

Used by `scripts/start-devcontainer-cursor.sh` with DevPod + Cursor.

## Host bind mounts

| Mount | Source | Platforms |
| ----- | ------ | --------- |
| Git config | `${localEnv:HOME}${localEnv:USERPROFILE}/.gitconfig` (read-only) | Linux, macOS, Windows |
| GPG agent socket | `${localEnv:XDG_RUNTIME_DIR}/gnupg/S.gpg-agent.extra` | **Linux only** |
| GPG trustdb | `${localEnv:HOME}/.gnupg/trustdb.gpg` | Linux, macOS, Windows (optional file) |

## GPG agent forwarding (Linux only)

The GPG agent bind mount relies on `XDG_RUNTIME_DIR`, which systemd sets on Linux
(typically `/run/user/<uid>`). It is usually **not** set on macOS or Windows.

If `XDG_RUNTIME_DIR` is empty, the mount source resolves to `/gnupg/S.gpg-agent.extra`,
which does not exist, and **devcontainer creation fails**.

### Linux

Before `devpod up --recreate`, ensure the host agent is running:

```bash
gpg -K
```

Host `~/.gitconfig` is mounted read-only. Git LFS filters are configured in the
repository (`.git/config`) via `git lfs install --local` in `setup-git-lfs.sh`.

`scripts/setup-container-gpg.sh` (postCreate) symlinks the host agent socket to
`~/.gnupg/S.gpg-agent`, copies the host `trustdb.gpg` into a **writable** local file
(readonly bind mounts cannot be symlink targets for imports), and imports
`public_gpg_keys/*.asc`.

## One-time setup (postCreateCommand)

These run once per devcontainer create (not on every shell):

- `uv sync --dev --all-packages`
- `scripts/install-dev-hooks.sh` (pre-commit + Git LFS hooks)
- `scripts/setup-container-gpg.sh` (host agent + trustdb + public keys)

`scripts/load-env.sh` is sourced from `~/.bashrc` and only handles PATH, aliases, and
environment variables (including SOPS decryption when needed).

For a **local clone outside devcontainers**, run once after `uv sync`:

```bash
./scripts/install-dev-hooks.sh
./scripts/import-public-gpg-keys.sh
```

### macOS / Windows

This devcontainer variant does not support host GPG agent forwarding. Options:

1. **Decrypt secrets on the host** before starting the container (recommended):

   ```bash
   sops -d .env.integration.enc > .env
   ```

   `scripts/load-env.sh` skips SOPS decryption when `.env` already exists.

2. **Remove the GPG-related `mounts` entries** from `devcontainer.json` (and rely on
   option 1 or on `public_gpg_keys/` for encrypt-only workflows).

DevPod's `--gpg-agent-forwarding` flag is not used here; it is a separate code path and
was found unreliable on some Linux hosts.
