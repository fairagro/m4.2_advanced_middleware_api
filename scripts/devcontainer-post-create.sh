#!/usr/bin/env bash
# Sequential Dev Container postCreate setup (also usable after a local clone).
# Invoked from .devcontainer/devcontainer.json as a single argv command.
#
# Keeps scripts/setup-git-lfs.sh as a separate entry point (AGENTS.md / re-runnable).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

load_env_line="source ${repo_root}/scripts/load-env.sh"
ruff_extension_id="charliermarsh.ruff"

find_remote_cli() {
    local candidate
    while IFS= read -r candidate; do
        echo "$candidate"
        return 0
    done < <(find "${HOME}/.cursor-server/bin" -path '*/bin/remote-cli/cursor' -type f 2>/dev/null | sort -r)

    while IFS= read -r candidate; do
        echo "$candidate"
        return 0
    done < <(find "${HOME}/.vscode-server/bin" -path '*/bin/remote-cli/code' -type f 2>/dev/null | sort -r)

    return 1
}

# ── commandhistory (Dev Container volume only) ───────────────────────────────
if [ -d /commandhistory ]; then
    echo "==> Fix commandhistory permissions"
    sudo chown -R "$(id -u):$(id -g)" /commandhistory
fi

# ── Python dependencies ─────────────────────────────────────────────────────
echo "==> Sync Python dependencies"
if [ -d .venv/bin ] && ! .venv/bin/python3 -c 'import sys' &>/dev/null; then
    echo "Removing stale .venv (broken Python interpreter)..."
    rm -rf .venv
fi
uv sync --dev --all-packages

if [ -d "${repo_root}/.venv/bin" ]; then
    export PATH="${repo_root}/.venv/bin:${PATH}"
fi

# ── pre-commit + Git LFS hooks ───────────────────────────────────────────────
echo "==> Install pre-commit hook"
if ! command -v pre-commit &>/dev/null; then
    echo "pre-commit not available after uv sync" >&2
    exit 1
fi
if [ ! -f "${repo_root}/.git/hooks/pre-commit" ]; then
    pre-commit install --hook-type pre-commit
else
    echo "pre-commit hook already installed"
fi

echo "==> Install Git LFS hooks"
bash "${script_dir}/setup-git-lfs.sh"

# ── public GPG keys (SOPS encrypt / recipient checks) ────────────────────────
echo "==> Import public GPG keys"
shopt -s nullglob
public_keys=( "${repo_root}/public_gpg_keys"/*.asc )
if [ ${#public_keys[@]} -gt 0 ]; then
    for key_file in "${public_keys[@]}"; do
        gpg --batch --import "${key_file}"
    done
else
    echo "No public_gpg_keys/*.asc found; skipping"
fi
shopt -u nullglob

# ── Ruff IDE extension (Cursor/VS Code remote only) ──────────────────────────
echo "==> Install Ruff extension (remote CLI)"
if remote_cli="$(find_remote_cli)"; then
    if "$remote_cli" --list-extensions 2>/dev/null | grep -qxF "${ruff_extension_id}"; then
        echo "${ruff_extension_id} already installed"
    else
        echo "Installing ${ruff_extension_id} via remote CLI..."
        if ! "$remote_cli" --install-extension "${ruff_extension_id}" --force; then
            echo "WARNING: Ruff extension install failed; use 'uv run ruff' or ./scripts/quality-fix.sh" >&2
        fi
    fi
else
    echo "No Cursor/VS Code remote CLI; skipping Ruff extension install"
fi

# ── bashrc ───────────────────────────────────────────────────────────────────
echo "==> Ensure load-env.sh is sourced from ~/.bashrc"
if [ -f "${HOME}/.bashrc" ] && ! grep -qF "${load_env_line}" "${HOME}/.bashrc"; then
    echo "${load_env_line}" >> "${HOME}/.bashrc"
fi

echo "==> Dev environment setup complete"
