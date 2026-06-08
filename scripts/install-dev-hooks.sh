#!/usr/bin/env bash
# One-time dev setup: pre-commit and Git LFS hooks. Run from devcontainer postCreate
# or manually after clone (local or container).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

if [ -d "${repo_root}/.venv/bin" ]; then
    export PATH="${repo_root}/.venv/bin:${PATH}"
fi

if ! command -v pre-commit &>/dev/null; then
    echo "⚠️ pre-commit not available — run: uv sync --dev --all-packages" >&2
    exit 1
fi

if [ ! -f "${repo_root}/.git/hooks/pre-commit" ]; then
    echo "🔧 Installing pre-commit hooks..."
    (cd "${repo_root}" && pre-commit install --hook-type pre-commit)
else
    echo "✅ pre-commit hook already installed"
fi

echo "🔧 Setting up Git LFS hooks..."
bash "${script_dir}/setup-git-lfs.sh"

echo "✅ Dev hooks installed"
