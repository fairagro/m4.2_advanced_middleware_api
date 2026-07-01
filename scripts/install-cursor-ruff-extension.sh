#!/usr/bin/env bash
# Install charliermarsh.ruff in Cursor remote/devcontainer via CLI.
#
# Cursor's marketplace UI can hang on "Installing" for Ruff because the extension
# depends on ms-python.python and Cursor's dependency resolver can loop on remapped
# Python/Pylance IDs (see astral-sh/ruff-vscode#943). Installing via the remote
# CLI bypasses that gallery traversal.
#
# No-op when not in a Cursor remote session (e.g. VS Code devcontainer).

set -euo pipefail

extension_id="charliermarsh.ruff"

cursor_cli=""
while IFS= read -r candidate; do
    cursor_cli="$candidate"
    break
done < <(find "${HOME}/.cursor-server/bin" -path '*/bin/remote-cli/cursor' -type f 2>/dev/null | sort -r)

if [[ -z "$cursor_cli" ]]; then
    echo "install-cursor-ruff-extension: no Cursor remote CLI; skipping (not a Cursor session)."
    exit 0
fi

if "$cursor_cli" --list-extensions 2>/dev/null | grep -qxF "$extension_id"; then
    echo "install-cursor-ruff-extension: ${extension_id} already installed."
    exit 0
fi

echo "install-cursor-ruff-extension: installing ${extension_id} via Cursor CLI..."
if "$cursor_cli" --install-extension "$extension_id" --force; then
    echo "install-cursor-ruff-extension: ${extension_id} installed."
else
    echo "install-cursor-ruff-extension: WARNING: install failed; use format/lint via 'uv run ruff' or ./scripts/quality-fix.sh" >&2
    exit 0
fi
