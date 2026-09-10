#!/usr/bin/env bash
# Copy version-controlled project git hooks into .git/hooks/ (pre-push quality gate).
# Does not install or require Git LFS — products that need LFS install it locally.
#
# Environment: host or Dev Container (needs uv/pre-commit for the quality stage on push).
#
# Usage (from any cwd):
#   ./scripts/setup-git-hooks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SOURCE_DIR="${REPO_ROOT}/scripts/git-hooks"
HOOKS_TARGET_DIR="${REPO_ROOT}/.git/hooks"

echo "Setting up project git hooks..."

if [[ ! -d "${REPO_ROOT}/.git" ]]; then
  echo "ERROR: not a git worktree root: ${REPO_ROOT}" >&2
  exit 1
fi

if [[ ! -d "${HOOKS_SOURCE_DIR}" ]]; then
  echo "ERROR: missing hooks source dir: ${HOOKS_SOURCE_DIR}" >&2
  exit 1
fi

mkdir -p "${HOOKS_TARGET_DIR}"

source_hook="${HOOKS_SOURCE_DIR}/pre-push"
target_hook="${HOOKS_TARGET_DIR}/pre-push"
if [[ -f "${source_hook}" ]]; then
  echo "Installing pre-push hook"
  cp "${source_hook}" "${target_hook}"
  chmod +x "${target_hook}"
else
  echo "ERROR: missing ${source_hook}" >&2
  exit 1
fi

# Remove legacy LFS-only hooks if a previous setup installed them.
for legacy in post-checkout post-commit post-merge; do
  legacy_target="${HOOKS_TARGET_DIR}/${legacy}"
  if [[ -f "${legacy_target}" ]] && grep -q 'git lfs' "${legacy_target}" 2>/dev/null; then
    echo "Removing legacy LFS hook: ${legacy}"
    rm -f "${legacy_target}"
  fi
done

echo ""
echo "Project git hooks setup complete."
echo "Installed:"
ls -la "${HOOKS_TARGET_DIR}/pre-push" 2>/dev/null || true
echo ""
echo "Commit-stage hooks remain: uv run pre-commit install --hook-type pre-commit"
echo "Products that need Git LFS: install git-lfs in a product-owned path (not this shared script)."
