#!/usr/bin/env bash
# Install Devinfra-owned pre-push dispatcher + quality fragment into .git/hooks/.
# Does not install, require, or manage Git LFS — LFS is entirely product-owned.
# Leaves foreign .git/hooks/pre-push.d/* fragments and non-pre-push hooks alone.
#
# Environment: host or Dev Container (needs uv/pre-commit for the quality stage on push).
#
# Usage (from any cwd):
#   ./scripts/setup-git-hooks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SOURCE_DIR="${REPO_ROOT}/scripts/git-hooks"
HOOKS_TARGET_DIR="${REPO_ROOT}/.git/hooks"
QUALITY_NAME="50-quality"

echo "Setting up project git hooks..."

if [[ ! -d "${REPO_ROOT}/.git" ]]; then
  echo "ERROR: not a git worktree root: ${REPO_ROOT}" >&2
  exit 1
fi

if [[ ! -d "${HOOKS_SOURCE_DIR}" ]]; then
  echo "ERROR: missing hooks source dir: ${HOOKS_SOURCE_DIR}" >&2
  exit 1
fi

source_dispatcher="${HOOKS_SOURCE_DIR}/pre-push"
source_quality="${HOOKS_SOURCE_DIR}/pre-push.d/${QUALITY_NAME}"
if [[ ! -f "${source_dispatcher}" ]]; then
  echo "ERROR: missing ${source_dispatcher}" >&2
  exit 1
fi
if [[ ! -f "${source_quality}" ]]; then
  echo "ERROR: missing ${source_quality}" >&2
  exit 1
fi

mkdir -p "${HOOKS_TARGET_DIR}/pre-push.d"

echo "Installing pre-push dispatcher"
cp "${source_dispatcher}" "${HOOKS_TARGET_DIR}/pre-push"
chmod +x "${HOOKS_TARGET_DIR}/pre-push"

echo "Installing pre-push.d/${QUALITY_NAME}"
cp "${source_quality}" "${HOOKS_TARGET_DIR}/pre-push.d/${QUALITY_NAME}"
chmod +x "${HOOKS_TARGET_DIR}/pre-push.d/${QUALITY_NAME}"

echo ""
echo "Project git hooks setup complete."
echo "Installed:"
ls -la "${HOOKS_TARGET_DIR}/pre-push" "${HOOKS_TARGET_DIR}/pre-push.d/${QUALITY_NAME}" 2>/dev/null || true
echo ""
echo "Commit-stage hooks remain: uv run pre-commit install --hook-type pre-commit"
