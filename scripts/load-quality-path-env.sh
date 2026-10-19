#!/usr/bin/env bash
# Load MYPYPATH / PYLINT_SOURCE_ROOTS from a product env file on every invoke.
# Only those keys are read (no full `source` of the file). Missing file = no-op.
#
# File wins over a pre-existing process value so a stale Dev Container env_file
# snapshot (Compose applies product.env only at create) cannot shadow an updated
# .devcontainer/product.env. Prefer product.env as the single source; CI should
# use quality_env_file / the same keys rather than relying on process-env wins.
#
# Usage:
#   source scripts/load-quality-path-env.sh [path-to-env-file]
# Default file: .devcontainer/product.env (relative to repo root / cwd when sourced).

_load_quality_path_env() {
  local env_file="${1:-.devcontainer/product.env}"
  local line key val

  if [[ ! -f "${env_file}" ]]; then
    return 0
  fi

  while IFS= read -r line || [[ -n "${line}" ]]; do
    # trim CR; skip blank/comments
    line="${line%$'\r'}"
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${line}" =~ ^[[:space:]]*(MYPYPATH|PYLINT_SOURCE_ROOTS)[[:space:]]*=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    # strip optional surrounding quotes
    if [[ "${val}" =~ ^\"(.*)\"$ ]]; then
      val="${BASH_REMATCH[1]}"
    elif [[ "${val}" =~ ^\'(.*)\'$ ]]; then
      val="${BASH_REMATCH[1]}"
    fi
    export "${key}=${val}"
  done <"${env_file}"
}

# When executed (not sourced), print exports for debugging / CI eval.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  set -euo pipefail
  _load_quality_path_env "${1:-.devcontainer/product.env}"
  printf 'MYPYPATH=%s\n' "${MYPYPATH-}"
  printf 'PYLINT_SOURCE_ROOTS=%s\n' "${PYLINT_SOURCE_ROOTS-}"
else
  _load_quality_path_env "${1:-.devcontainer/product.env}"
fi
