#!/usr/bin/env bash
#
# Start the development environment with encrypted secrets
#
# Usage:
#   ./start.sh              # Start all services
#   ./start.sh --build      # Build images and start
#

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

repo_root="$(cd "${script_dir}/.." && pwd)"
python_version_file="${repo_root}/.python-version"
alpine_version_file="${repo_root}/.alpine-version"

[[ -f "${python_version_file}" ]] || {
  echo "ERROR: Python version file not found: ${python_version_file}" >&2
  exit 1
}
[[ -f "${alpine_version_file}" ]] || {
  echo "ERROR: Alpine version file not found: ${alpine_version_file}" >&2
  exit 1
}

# Pins from repo-root version files (docker/Dockerfile.api build-args)
export PYTHON_VERSION ALPINE_VERSION ALPINE_MINOR
PYTHON_VERSION="$(tr -d '[:space:]' < "${python_version_file}")"
ALPINE_VERSION="$(tr -d '[:space:]' < "${alpine_version_file}")"
[[ "${PYTHON_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: .python-version must be a patch pin X.Y.Z (got: '${PYTHON_VERSION:-<empty>}')" >&2
  exit 1
}
[[ "${ALPINE_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: .alpine-version must be a patch pin X.Y.Z (got: '${ALPINE_VERSION:-<empty>}')" >&2
  exit 1
}
ALPINE_MINOR="${ALPINE_VERSION%.*}"

# Parse arguments
BUILD_FLAG=""
if [[ "${1:-}" == "--build" || "${1:-}" == "--rebuild" ]]; then
  BUILD_FLAG="--build"
fi

echo "==> Starting development environment..."
echo "    - Python ${PYTHON_VERSION} (from .python-version)"
echo "    - Alpine ${ALPINE_VERSION} / minor ${ALPINE_MINOR} (from .alpine-version)"
echo "    - PostgreSQL will be started"
echo "    - Database will be initialized with Edaphobase dump"
echo ""

# Check if sops is available
if ! command -v sops &> /dev/null; then
  echo "ERROR: sops is not installed or not in PATH"
  echo "Install sops: https://github.com/getsops/sops"
  exit 1
fi

echo "==> Starting services with sops exec-env..."
echo "    Environment variable 'data' will contain decrypted client.key"
echo ""

# Use sops exec-env to decrypt and run docker compose
# We need to preserve TERM and PATH for proper terminal support
# Use exec-env without --pristine but ensure minimal env pollution
sops exec-env "${script_dir}/secrets.enc.yaml" \
  "docker compose up $BUILD_FLAG"

echo ""
echo "==> Services finished!"
echo "    - View logs: docker compose logs"
echo "    - Clean up: docker compose down"
