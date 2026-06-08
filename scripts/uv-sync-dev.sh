#!/usr/bin/env bash
# Dev dependency sync for devcontainer postCreate and local use.
# Drops a stale .venv when its Python interpreter is missing (common after image rebuild).

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

if [ -d .venv/bin ] && ! .venv/bin/python3 -c 'import sys' &>/dev/null; then
    echo "Removing stale .venv (broken Python interpreter)..."
    rm -rf .venv
fi

exec uv sync --dev --all-packages
