#!/usr/bin/env bash
# Sequential Dev Container postCreate setup.
# Environment: Linux Dev Container only (invoked from .devcontainer/devcontainer.json).
#
# Generic shared-infra / product sync — no product workspace name hardcoding (issue #10).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

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

install_extension_soft() {
  local ext_id="$1"
  local remote_cli="$2"
  if "$remote_cli" --list-extensions 2>/dev/null | grep -qxF "${ext_id}"; then
    echo "${ext_id} already installed"
    return 0
  fi
  echo "Installing ${ext_id} via remote CLI..."
  if ! "$remote_cli" --install-extension "${ext_id}" --force; then
    echo "WARNING: extension install failed for ${ext_id}" >&2
  fi
}

# ── commandhistory (Dev Container volume only) ───────────────────────────────
if [ -d /commandhistory ]; then
  echo "==> Fix commandhistory permissions"
  sudo chown -R "$(id -u):$(id -g)" /commandhistory
fi

# ── gh config volume ─────────────────────────────────────────────────────────
if [ -d /home/vscode/.config/gh ] || [ -e /home/vscode/.config ]; then
  echo "==> Fix gh config permissions"
  sudo mkdir -p /home/vscode/.config/gh
  sudo chown -R "$(id -u):$(id -g)" /home/vscode/.config
fi

# ── versions.env → .python-version ───────────────────────────────────────────
echo "==> Sync versions from versions.env"
# shellcheck disable=SC1091
source "${script_dir}/load-versions-env.sh"

# Tokens for interactive use come from scripts/bin/{gh,git} (PATH via remoteEnv).
echo "==> Load stored personal tokens into this postCreate environment (no TTY prompt)"
token_src="${repo_root}/scripts/dev-tokens.sh"
if [ -f "${token_src}" ]; then
  # shellcheck disable=SC1091
  source "${token_src}" || true
fi

# ── Python dependencies ─────────────────────────────────────────────────────
if [ -f "${repo_root}/pyproject.toml" ]; then
  echo "==> Sync Python dependencies (uv)"
  if [ -d .venv/bin ] && ! .venv/bin/python3 -c 'import sys' &>/dev/null; then
    echo "Removing stale .venv (broken Python interpreter)..."
    rm -rf .venv
  fi
  uv sync
  if [ -d "${repo_root}/.venv/bin" ]; then
    export PATH="${repo_root}/.venv/bin:${PATH}"
  fi
fi

# ── pre-commit commit-stage hook ─────────────────────────────────────────────
echo "==> Install pre-commit hook (commit-stage)"
if command -v pre-commit >/dev/null 2>&1 || uv run pre-commit --version >/dev/null 2>&1; then
  if [ ! -f "${repo_root}/.git/hooks/pre-commit" ]; then
    uv run pre-commit install --hook-type pre-commit
  else
    echo "pre-commit hook already installed"
  fi
else
  echo "WARNING: pre-commit not available after uv sync" >&2
fi

# ── Project pre-push git hooks ───────────────────────────────────────────────
echo "==> Install project git hooks"
bash "${script_dir}/setup-git-hooks.sh"

# ── public GPG keys (SOPS encrypt / recipient checks) ────────────────────────
echo "==> Import public GPG keys (if present)"
shopt -s nullglob
public_keys=( "${repo_root}/public_gpg_keys"/*.asc )
if [ ${#public_keys[@]} -gt 0 ]; then
  for key_file in "${public_keys[@]}"; do
    gpg --batch --import "${key_file}" || echo "WARNING: failed to import ${key_file}" >&2
  done
else
  echo "No public_gpg_keys/*.asc found; skipping"
fi
shopt -u nullglob

# ── IDE extensions (Cursor/VS Code remote only; soft-fail) ───────────────────
# Keep in sync with .devcontainer/devcontainer.json → customizations.vscode.extensions
# (union of shared product-repo needs + Devinfra markdown/hadolint extras).
echo "==> Install recommended IDE extensions (remote CLI)"
extensions=(
  jeff-hykin.better-dockerfile-syntax
  ms-azuretools.vscode-docker
  formulahendry.docker-explorer
  exiasr.hadolint
  esbenp.prettier-vscode
  davidanson.vscode-markdownlint
  signageos.signageos-vscode-sops
  samuelcolvin.jinjahtml
  redhat.vscode-yaml
  tamasfe.even-better-toml
  ms-python.python
  ms-python.vscode-pylance
  ms-python.debugpy
  ms-python.vscode-python-envs
  ms-python.pylint
  ms-python.mypy-type-checker
  charliermarsh.ruff
  mhutchie.git-graph
  donjayamanne.githistory
  codezombiech.gitignore
  github.copilot-chat
  github.vscode-github-actions
  tim-koehler.helm-intellisense
  vadzimnestsiarenka.helm-template-preview-and-more
  jebbs.plantuml
)
if remote_cli="$(find_remote_cli)"; then
  for ext in "${extensions[@]}"; do
    install_extension_soft "${ext}" "${remote_cli}"
  done
else
  echo "No Cursor/VS Code remote CLI; skipping extension installs (devcontainer.json still recommends them)"
fi

echo "==> Dev Container post-create done"
echo "    gh=$(command -v gh || echo missing)  openspec=$(command -v openspec || echo missing)  uv=$(command -v uv || echo missing)"
echo "    node=$(command -v node || echo missing)  prettier=$(command -v prettier || echo missing)"
echo "    sops=$(command -v sops || echo missing)  trivy=$(command -v trivy || echo missing)  renovate=$(command -v renovate || echo missing)"
echo "    scripts/bin on PATH via remoteEnv after rebuild"
