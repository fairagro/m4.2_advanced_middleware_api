#!/usr/bin/env bash
# Run a fleet quality CLI with pins from scripts/quality-tools-pins.txt.
# Does not require the tool in the product pyproject. Usage:
#   ./scripts/run-quality-cli.sh <tool> [args...]
# Example:
#   ./scripts/run-quality-cli.sh ruff check --config ruff.toml middleware/

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
exec uv run --with-requirements "${REQ}" -- "$@"
