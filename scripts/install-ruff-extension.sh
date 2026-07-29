#!/usr/bin/env bash
# Install charliermarsh.ruff in a Cursor or VS Code remote/devcontainer via CLI.
#
# Cursor's marketplace UI can hang on "Installing" for Ruff because the extension
# depends on ms-python.python and Cursor's dependency resolver can loop on remapped
# Python/Pylance IDs (see astral-sh/ruff-vscode#943). Installing via the remote
# CLI bypasses that gallery traversal. VS Code uses the same approach so Ruff does
# not need to be listed in devcontainer.json extensions (avoids the Cursor hang).
#
# No-op when neither remote CLI is present.

set -euo pipefail

extension_id="charliermarsh.ruff"

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

remote_cli=""
if remote_cli="$(find_remote_cli)"; then
    :
else
    echo "install-ruff-extension: no Cursor/VS Code remote CLI; skipping."
    exit 0
fi

if "$remote_cli" --list-extensions 2>/dev/null | grep -qxF "$extension_id"; then
    echo "install-ruff-extension: ${extension_id} already installed."
    exit 0
fi

echo "install-ruff-extension: installing ${extension_id} via remote CLI..."
if "$remote_cli" --install-extension "$extension_id" --force; then
    echo "install-ruff-extension: ${extension_id} installed."
else
    echo "install-ruff-extension: WARNING: install failed; use format/lint via 'uv run ruff' or ./scripts/quality-fix.sh" >&2
    exit 0
fi
