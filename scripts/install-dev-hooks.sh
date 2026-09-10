#!/usr/bin/env bash
# Product-local glue for hook/venv repair after path drift.
# Not a synced script — do not fold product-only behaviour into shared
# scripts/devcontainer-post-create.sh (m4.2_middleware_devinfra#56, #58).
#
# Calls:
#   - uv sync --dev --all-packages   (this workspace always needs both flags;
#     shared post-create must gain them via Devinfra #56, then this stays repair-only)
#   - pre-commit install             (commit-stage)
#   - scripts/setup-git-hooks.sh     (synced: quality pre-push only)
#
# Prefer Dev Container postCreate (synced script) for first install.
# Do not invoke from load-env.sh (per-shell).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"
venv_python="${repo_root}/.venv/bin/python"

_venv_script_shebang_stale() {
  local script="${1:?script path required}"
  [ ! -f "$script" ] && return 1
  local shebang
  shebang=$(head -n 1 "$script" | sed 's/^#!//')
  shebang=${shebang%% *}
  [ -n "$shebang" ] && [ ! -x "$shebang" ]
}

_venv_stale() {
  [ ! -d .venv/bin ] && return 1
  if ! .venv/bin/python -c 'import sys' &>/dev/null; then
    return 0
  fi
  _venv_script_shebang_stale .venv/bin/pre-commit
}

_venv_usable() {
  [ -x "$venv_python" ] && "$venv_python" -c 'pass' 2>/dev/null \
    && "$venv_python" -m pre_commit --version &>/dev/null
}

if _venv_stale || ! _venv_usable; then
  echo "Repairing .venv (uv sync --dev --all-packages)..."
  if _venv_stale; then
    rm -rf .venv
  fi
  uv sync --dev --all-packages
fi

if ! _venv_usable; then
  echo "WARNING: pre-commit unavailable — run: uv sync --dev --all-packages" >&2
  exit 1
fi

export PATH="${repo_root}/.venv/bin:${PATH}"

git_hooks_dir="$(git -C "${repo_root}" rev-parse --git-path hooks 2>/dev/null || echo ".git/hooks")"
[[ "$git_hooks_dir" = /* ]] || git_hooks_dir="${repo_root}/${git_hooks_dir}"
hook="${git_hooks_dir}/pre-commit"
if [ ! -f "$hook" ] || ! grep -Fq "INSTALL_PYTHON=${venv_python}" "$hook" 2>/dev/null; then
  echo "Installing pre-commit hooks..."
  (cd "${repo_root}" && "${venv_python}" -m pre_commit install --hook-type pre-commit)
else
  echo "pre-commit hook up to date"
fi

bash "${script_dir}/setup-git-hooks.sh"

echo "Dev hooks installed"
