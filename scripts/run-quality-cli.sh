#!/usr/bin/env bash
# Run a fleet quality CLI with pins from scripts/quality-tools-pins.txt.
# Does not require the tool in the product pyproject. Usage:
#   ./scripts/run-quality-cli.sh <tool> [args...]
# Example:
#   ./scripts/run-quality-cli.sh ruff check --config ruff.toml middleware/
#
# Soft-loads MYPYPATH / PYLINT_SOURCE_ROOTS from .devcontainer/product.env when unset
# (same keys as reusable code-quality; process env wins if already set).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQ="${SCRIPT_DIR}/quality-tools-pins.txt"

if [[ ! -f "${REQ}" ]]; then
  echo "ERROR: missing quality tool pins ${REQ}" >&2
  exit 1
fi

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 <tool> [args...]" >&2
  exit 2
fi

cd "${REPO_ROOT}"
# shellcheck source=scripts/load-quality-path-env.sh
source "${SCRIPT_DIR}/load-quality-path-env.sh" "${REPO_ROOT}/.devcontainer/product.env"

tool="$1"
shift
extra=()
if [[ "${tool}" == "pylint" && -n "${PYLINT_SOURCE_ROOTS:-}" ]]; then
  has_roots=0
  for a in "$@"; do
    if [[ "${a}" == --source-roots || "${a}" == --source-roots=* ]]; then
      has_roots=1
      break
    fi
  done
  if [[ "${has_roots}" -eq 0 ]]; then
    extra+=(--source-roots="${PYLINT_SOURCE_ROOTS}")
  fi
fi

exec uv run --with-requirements "${REQ}" -- "${tool}" "${extra[@]}" "$@"
