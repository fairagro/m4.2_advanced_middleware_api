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
# Pins from repo-root version files (docker/Dockerfile.api build-args)
export PYTHON_VERSION ALPINE_VERSION ALPINE_MINOR
PYTHON_VERSION="$(tr -d '[:space:]' < "${repo_root}/.python-version")"
ALPINE_VERSION="$(tr -d '[:space:]' < "${repo_root}/.alpine-version")"
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
