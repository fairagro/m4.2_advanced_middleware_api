#!/usr/bin/env bash
# Load repo-root versions.env and sync .python-version from PYTHON_VERSION.
#
# Environment: host or Dev Container.
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
# shellcheck source=/dev/null
source "${VERSIONS_ENV}"
set +a

if [[ ! "${PYTHON_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: PYTHON_VERSION must be X.Y.Z in versions.env (got: '${PYTHON_VERSION:-<empty>}')" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ -z "${UV_VERSION:-}" ]]; then
  echo "ERROR: UV_VERSION must be set in versions.env" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ -z "${NODE_VERSION:-}" || -z "${OPENSPEC_VERSION:-}" ]]; then
  echo "ERROR: NODE_VERSION and OPENSPEC_VERSION must be set in versions.env" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ -z "${PRETTIER_VERSION:-}" || -z "${MARKDOWNLINT_CLI2_VERSION:-}" ]]; then
  echo "ERROR: PRETTIER_VERSION and MARKDOWNLINT_CLI2_VERSION must be set in versions.env" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ -z "${PIP_VERSION:-}" || -z "${ALPINE_VERSION:-}" || -z "${ALPINE_MINOR:-}" || -z "${PYINSTALLER_VERSION:-}" ]]; then
  echo "ERROR: product-app image pins PIP_VERSION, ALPINE_VERSION, ALPINE_MINOR, PYINSTALLER_VERSION must be set in versions.env" >&2
  return 1 2>/dev/null || exit 1
fi

export PYTHON_VERSION UV_VERSION NODE_VERSION OPENSPEC_VERSION PRETTIER_VERSION MARKDOWNLINT_CLI2_VERSION
export PIP_VERSION ALPINE_VERSION ALPINE_MINOR PYINSTALLER_VERSION

# Keep uv / actions/setup-python pin file aligned with versions.env
printf '%s\n' "${PYTHON_VERSION}" > "${REPO_ROOT}/.python-version"
