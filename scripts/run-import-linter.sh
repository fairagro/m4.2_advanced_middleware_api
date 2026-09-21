#!/usr/bin/env bash
# Run import-linter with the synced baseline and optional product overlay.
# Environment: host or Dev Container (needs uv + import-linter in the project env).
#
# Baseline: `.importlinter.global` (synced)
# Overlay:  `.importlinter` (product-owned; sync never overwrites) — contract sections only
#
# Soft-skips when `middleware/` is absent (e.g. Devinfra itself).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

BASELINE="${REPO_ROOT}/.importlinter.global"
OVERLAY="${REPO_ROOT}/.importlinter"

if [[ ! -d "${REPO_ROOT}/middleware" ]]; then
  echo "WARNING: skipping import-linter (no middleware/ package tree)." >&2
  exit 0
fi

if [[ ! -f "${BASELINE}" ]]; then
  echo "ERROR: missing synced baseline ${BASELINE}" >&2
  exit 1
fi

TMP=""
cleanup() {
  if [[ -n "${TMP}" && -f "${TMP}" ]]; then
    rm -f "${TMP}"
  fi
}
trap cleanup EXIT

CONFIG="${BASELINE}"

if [[ -f "${OVERLAY}" ]]; then
  if grep -q '^\[importlinter\][[:space:]]*$' "${OVERLAY}"; then
    echo "WARNING: ${OVERLAY} contains [importlinter] globals; only [importlinter:contract:…] sections are merged." >&2
  fi
  TMP="$(mktemp "${TMPDIR:-/tmp}/importlinter.XXXXXX")"
  cat "${BASELINE}" >"${TMP}"
  printf '\n' >>"${TMP}"
  # Append product contract sections only (keep=1 inside [importlinter:contract:…]).
  awk '
    /^\[importlinter:contract:/ { keep = 1 }
    /^\[/ && !/^\[importlinter:contract:/ { keep = 0 }
    keep { print }
  ' "${OVERLAY}" >>"${TMP}"
  CONFIG="${TMP}"
fi

uv run lint-imports --config "${CONFIG}"
