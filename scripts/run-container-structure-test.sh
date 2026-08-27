#!/bin/bash
set -e

PYTHON_VERSION="$(tr -d '[:space:]' < .python-version)"
ALPINE_VERSION="$(tr -d '[:space:]' < .alpine-version)"
ALPINE_MINOR="${ALPINE_VERSION%.*}"

echo "🔧 Building Docker image for container structure test (Python ${PYTHON_VERSION}, Alpine ${ALPINE_VERSION})..."
docker build -f docker/Dockerfile.api \
  --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
  --build-arg "ALPINE_VERSION=${ALPINE_VERSION}" \
  --build-arg "ALPINE_MINOR=${ALPINE_MINOR}" \
  -t fairagro-advanced-middleware-api:test .

echo "🔍 Running Container Structure Test..."
container-structure-test test \
    --image fairagro-advanced-middleware-api:test \
    --config docker/container-structure-tests/api.yaml
