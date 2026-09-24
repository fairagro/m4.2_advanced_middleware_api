#!/usr/bin/env bash
# Run import-linter against the product-owned `.importlinter`.
# Soft-skips when `middleware/` is absent (e.g. Devinfra). Fleet CLI via run-quality-cli.sh.
# Required settings: docs/quality.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

CONFIG="${REPO_ROOT}/.importlinter"

if [[ ! -d "${REPO_ROOT}/middleware" ]]; then
  echo "WARNING: skipping import-linter (no middleware/ package tree)." >&2
  exit 0
fi

if [[ ! -f "${CONFIG}" ]]; then
  echo "ERROR: missing product .importlinter — adopt fleet settings from docs/quality.md" >&2
  exit 1
fi

exec bash "${SCRIPT_DIR}/run-quality-cli.sh" lint-imports --config "${CONFIG}"
