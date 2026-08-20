#!/usr/bin/env bash
# Apply autofixes using the same hooks as pre-commit (commit stage).
# Runs only mutating hooks; does not run mypy/pylint/bandit/ggshield/pre-push.
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

echo "🔧 Starting Code Quality Fixes (pre-commit autofix hooks)..."
echo "================================="

# Hooks that rewrite files (same IDs / config as .pre-commit-config.yaml).
# ruff uses --fix --exit-non-zero-on-fix, so a successful rewrite may exit 1.
autofix_hooks=(
    trailing-whitespace
    end-of-file-fixer
    ruff
    ruff-format
)

worst_code=0
for hook in "${autofix_hooks[@]}"; do
    echo -e "${YELLOW}🔧 ${hook}...${NC}"
    set +e
    run_pre_commit "${hook}" --all-files
    code=$?
    set -e
    if [ "${code}" -gt "${worst_code}" ]; then
        worst_code="${code}"
    fi
done

if [ "${worst_code}" -eq 0 ]; then
    echo -e "${GREEN}🎉 Autofix hooks completed (no further changes).${NC}"
elif [ "${worst_code}" -eq 1 ]; then
    # pre-commit / ruff exit 1 when files were modified — expected for a fix script.
    echo -e "${GREEN}🎉 Autofixes applied (re-run quality-check / commit).${NC}"
else
    echo -e "${RED}❌ Autofix hooks failed (exit ${worst_code}).${NC}"
    exit "${worst_code}"
fi

echo "Verify with the commit-stage gate:"
echo "./scripts/quality-check.sh"
