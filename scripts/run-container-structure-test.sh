#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# shellcheck source=load-versions-env.sh
source "${SCRIPT_DIR}/load-versions-env.sh"

echo "🔧 Building Docker image for container structure test (Python ${PYTHON_VERSION}, Alpine ${ALPINE_VERSION})..."
docker build -f docker/Dockerfile.api \
  --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
  --build-arg "ALPINE_VERSION=${ALPINE_VERSION}" \
  --build-arg "ALPINE_MINOR=${ALPINE_MINOR}" \
  --build-arg "PIP_VERSION=${PIP_VERSION}" \
  --build-arg "UV_VERSION=${UV_VERSION}" \
  -t fairagro-advanced-middleware-api:test .

echo "🔍 Running Container Structure Test..."
container-structure-test test \
    --image fairagro-advanced-middleware-api:test \
    --config docker/container-structure-tests/api.yaml
