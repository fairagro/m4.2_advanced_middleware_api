#!/usr/bin/env bash
# Load repo-root versions.env, validate runtime pins, derive ALPINE_MINOR,
# and sync .python-version from PYTHON_VERSION.
#
# Alpine stays only in versions.env (no .alpine-version file): nothing outside
# this loader/Docker build-args consumes a dedicated Alpine pin file. Python
# still needs .python-version for uv / actions/setup-python.
#
# Usage (from any cwd):
#   source "$(git rev-parse --show-toplevel)/scripts/load-versions-env.sh"
# or:
#   source /path/to/repo/scripts/load-versions-env.sh

_load_versions_env_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${_load_versions_env_script_dir}/.." && pwd)"
VERSIONS_ENV="${REPO_ROOT}/versions.env"

if [[ ! -f "${VERSIONS_ENV}" ]]; then
  echo "ERROR: versions.env not found: ${VERSIONS_ENV}" >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
set -a
source "${VERSIONS_ENV}"
set +a

if [[ ! "${PYTHON_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: PYTHON_VERSION must be X.Y.Z in versions.env (got: '${PYTHON_VERSION:-<empty>}')" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ ! "${ALPINE_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: ALPINE_VERSION must be X.Y.Z in versions.env (got: '${ALPINE_VERSION:-<empty>}')" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ -z "${UV_VERSION:-}" || -z "${PIP_VERSION:-}" ]]; then
  echo "ERROR: UV_VERSION and PIP_VERSION must be set in versions.env" >&2
  return 1 2>/dev/null || exit 1
fi

ALPINE_MINOR="${ALPINE_VERSION%.*}"
export PYTHON_VERSION ALPINE_VERSION ALPINE_MINOR UV_VERSION PIP_VERSION

# Keep uv / setup-python pin file aligned with versions.env
printf '%s\n' "${PYTHON_VERSION}" > "${REPO_ROOT}/.python-version"
