#!/usr/bin/env bash
#
# Stop all services and optionally clean up volumes
#
# Usage:
#   ./stop.sh           # Stop services, keep data
#   ./stop.sh --clean   # Stop services and remove all data
#

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [[ "${1:-}" == "--clean" ]]; then
  echo "==> Stopping services and removing all data..."
  docker compose down -v
  echo "==> All services stopped and data removed."
else
  echo "==> Stopping services (data will be preserved)..."
  docker compose down
  echo "==> Services stopped. Data preserved in volumes."
  echo "    To remove data: ./stop.sh --clean"
fi
