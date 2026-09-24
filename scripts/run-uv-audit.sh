#!/usr/bin/env bash
# Audit the project lockfile with `uv audit` (fleet Python CVE gate vs Trivy images).
# Optional product overlay `.uv-audit-ignore`: one advisory ID per line (# comments / blanks ok).
#
# Environment: host or Dev Container (needs network to OSV). Escape hatch: SKIP=uv-audit.
#
# Usage:
#   ./scripts/run-uv-audit.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

IGNORE_FILE="${REPO_ROOT}/.uv-audit-ignore"
IGNORE_ARGS=()

if [[ -f "${IGNORE_FILE}" ]]; then
  while IFS= read -r line || [[ -n "${line}" ]]; do
    # trim
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    IGNORE_ARGS+=(--ignore "${line}")
  done <"${IGNORE_FILE}"
fi

# Preview on current uv pins; silence the experimental banner when supported.
exec uv audit --frozen --preview-features audit-command "${IGNORE_ARGS[@]}"
