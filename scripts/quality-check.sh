#!/usr/bin/env bash
# Commit-stage quality gate via pre-commit (non-mutating checks only).
# Does not run autofix hooks or pre-push (pytest, container-structure-test).
# Apply fixes with ./scripts/quality-fix.sh, then re-run this script.
#
# Environment: host or Dev Container (needs `uv`; markdownlint hook needs Node/`npm`;
# ggshield needs GITGUARDIAN_API_KEY in env). Host clones: run `npm install` once if
# markdownlint-cli2 is not on PATH. In the Dev Container, personal tokens load when
# /commandhistory exists.
#
# Usage: ./scripts/quality-check.sh

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

if [ -d "${repo_root}/.venv/bin" ]; then
  export PATH="${repo_root}/.venv/bin:${PATH}"
fi

# Optional: Dev Container token store (ggshield). Do not require it on host checkouts.
if [ -d /commandhistory ]; then
  # shellcheck source=scripts/dev-tokens.sh
  source "${repo_root}/scripts/dev-tokens.sh"
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Mutating commit-stage hooks — quality-fix.sh / git commit; not this check script.
# pre-commit SKIP is a comma-separated list of hook ids.
# ruff-format writes files; verify formatting separately with --check below.
export SKIP="${SKIP:+${SKIP},}trailing-whitespace,end-of-file-fixer,ruff-fix,ruff-format"

echo "Starting Code Quality Checks (pre-commit, commit stage, non-mutating)..."
echo "=================================="
echo -e "${YELLOW}pre-commit run --all-files (SKIP=${SKIP})...${NC}"

set +e
uv run pre-commit run --all-files
code=$?

# Format gate without mutating (the ruff-format hook rewrites; skipped above).
if [ -d middleware ]; then
  echo -e "${YELLOW}ruff format --check middleware/...${NC}"
  uv run ruff format --check --config ruff.toml middleware/
  fmt_code=$?
  # Keep the first non-zero exit (pre-commit) so CI does not only see the format gate code.
  if [ "${fmt_code}" -ne 0 ] && [ "${code}" -eq 0 ]; then
    code="${fmt_code}"
  fi
fi
set -e

if [ "${code}" -eq 0 ]; then
  echo -e "${GREEN}All non-mutating commit-stage hooks passed!${NC}"
  echo "================================="
  exit 0
fi

echo -e "${RED}pre-commit failed (exit ${code}).${NC}"
echo "Tip: apply autofixes with ./scripts/quality-fix.sh then re-run."
exit "${code}"
