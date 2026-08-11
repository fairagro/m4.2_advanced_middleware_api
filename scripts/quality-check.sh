#!/bin/bash
# Code Quality Check Script
# Mirrors GitHub Actions reusable-code-quality.yml (ruff / pylint / mypy / bandit).
# Does not run pytest or pre-push hooks — those stay in pre-push / CI.

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

print_status() {
    local label="$1"
    local code="$2"
    if [ "${code}" -eq 0 ]; then
        echo -e "${GREEN}✅ ${label} passed${NC}"
    else
        echo -e "${RED}❌ ${label} failed${NC}"
        exit "${code}"
    fi
}

run_check() {
    local label="$1"
    shift
    echo -e "${YELLOW}🔍 ${label}...${NC}"
    set +e
    "$@"
    local code=$?
    set -e
    print_status "${label}" "${code}"
}

echo "🔍 Starting Code Quality Checks (CI-parity)..."
echo "=================================="

run_check "Ruff format" \
    uv run ruff format --check --diff --config pyproject.toml middleware/
run_check "Ruff lint" \
    uv run ruff check --config pyproject.toml middleware/
run_check "Pylint" \
    uv run pylint --rcfile pyproject.toml middleware/
run_check "MyPy" \
    uv run mypy --config-file pyproject.toml middleware/

echo -e "${YELLOW}🔍 Bandit...${NC}"
bandit_report="$(mktemp)"
set +e
uv run bandit -r middleware/ -c .bandit -f json -o "${bandit_report}"
BANDIT_REPORT="${bandit_report}" python3 - <<'PY'
import json
import os
import sys

with open(os.environ["BANDIT_REPORT"], encoding="utf-8") as f:
    data = json.load(f)
for r in data.get("results", []):
    print(
        f"  [{r['issue_severity']:6}] {r['filename']}:{r['line_number']}: {r['issue_text']}"
    )
totals = data.get("metrics", {}).get("_totals", {})
low = int(totals.get("SEVERITY.LOW", 0) or 0)
med = int(totals.get("SEVERITY.MEDIUM", 0) or 0)
high = int(totals.get("SEVERITY.HIGH", 0) or 0)
print(f"Bandit findings: LOW={low}, MEDIUM={med}, HIGH={high}")
if med + high > 0:
    print(f"Failing: {med + high} MEDIUM/HIGH finding(s) found.")
    sys.exit(1)
PY
bandit_code=$?
set -e
rm -f "${bandit_report}"
print_status "Bandit" "${bandit_code}"

echo -e "${GREEN}🎉 All quality checks passed!${NC}"
echo "================================="
