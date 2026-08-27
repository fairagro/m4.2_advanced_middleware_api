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
# shellcheck source=../scripts/load-versions-env.sh
source "${repo_root}/scripts/load-versions-env.sh"

# Parse arguments
BUILD_FLAG=""
if [[ "${1:-}" == "--build" || "${1:-}" == "--rebuild" ]]; then
  BUILD_FLAG="--build"
fi

echo "==> Starting development environment..."
echo "    - Python ${PYTHON_VERSION} / Alpine ${ALPINE_VERSION} (from versions.env)"
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
