#!/usr/bin/env bash
#
# Start sql_to_arc locally with a local DB, but connecting to an EXTERNAL Middleware API.
#
# Usage:
#   ./start-external.sh              # Start services
#   ./start-external.sh --build      # Build images and start
#

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

# Parse arguments
BUILD_FLAG=""
if [[ "${1:-}" == "--build" ]]; then
  BUILD_FLAG="--build"
fi

echo "==> Starting SQL-to-ARC with EXTERNAL API..."
echo "    - Local PostgreSQL will be started"
echo "    - Database will be initialized with Edaphobase dump"
echo "    - SQL-to-ARC will connect to the API configured in config-external.yaml"
echo "    - Using client certificates: client.crt, client.key"
echo ""

if [[ ! -f "client.key" ]]; then
  echo "ERROR: client.key not found. Please provide your client key."
  exit 1
fi

# Use sops exec-env to pass the decrypted key as an environment variable
# without writing it to a physical disk file.
sops exec-env "${script_dir}/client.key" \
  "docker compose -f compose-external.yaml up --abort-on-container-exit sql_to_arc $BUILD_FLAG"

echo ""
echo "==> Services finished!"
echo "    - View logs: docker compose -f compose-external.yaml logs"
echo "    - Clean up: docker compose -f compose-external.yaml down"
