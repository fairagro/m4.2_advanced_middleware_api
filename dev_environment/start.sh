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

# Parse arguments
BUILD_FLAG=""
if [[ "${1:-}" == "--build" ]]; then
  BUILD_FLAG="--build"
fi

echo "==> Starting development environment..."
echo "    - PostgreSQL will be started"
echo "    - Database will be initialized with Edaphobase dump"
echo "    - SQL-to-ARC converter will run after initialization"
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
  "docker compose up --abort-on-container-exit sql_to_arc $BUILD_FLAG"

echo ""
echo "==> Services finished!"
echo "    - View logs: docker compose logs"
echo "    - Clean up: docker compose down"
