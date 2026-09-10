#!/usr/bin/env bash
# Apply autofixes using the same hooks as pre-commit (commit stage).
# Runs only mutating hooks; does not run mypy/pylint/bandit/ggshield/pre-push.
#
# Environment: host or Dev Container (needs `uv`).
#
# Usage: ./scripts/quality-fix.sh
# Then verify with: ./scripts/quality-check.sh

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

if [ -d "${repo_root}/.venv/bin" ]; then
  export PATH="${repo_root}/.venv/bin:${PATH}"
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

run_pre_commit() {
  uv run pre-commit run "$@"
}

echo "Starting Code Quality Fixes (pre-commit autofix hooks)..."
echo "================================="

# Hooks that rewrite files (same IDs / config as .pre-commit-config.yaml).
# ruff-fix exits 1 when it rewrote files — expected for a fix script.
autofix_hooks=(
  trailing-whitespace
  end-of-file-fixer
  ruff-fix
  ruff-format
)

worst_code=0
for hook in "${autofix_hooks[@]}"; do
  echo -e "${YELLOW}${hook}...${NC}"
  set +e
  run_pre_commit "${hook}" --all-files
  code=$?
  set -e
  if [ "${code}" -gt "${worst_code}" ]; then
    worst_code="${code}"
  fi
done

if [ "${worst_code}" -eq 0 ]; then
  echo -e "${GREEN}Autofix hooks completed (no further changes).${NC}"
elif [ "${worst_code}" -eq 1 ]; then
  # pre-commit uses 1 both when files were rewritten and when a hook failed — cannot tell apart.
  echo -e "${YELLOW}Autofix hooks exited 1 (rewrites and/or a hook failure). Re-run ./scripts/quality-check.sh.${NC}"
else
  echo -e "${RED}Autofix hooks failed (exit ${worst_code}).${NC}"
  exit "${worst_code}"
fi

echo "Verify with the commit-stage gate:"
echo "./scripts/quality-check.sh"
