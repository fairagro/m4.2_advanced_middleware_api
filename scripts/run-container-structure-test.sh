#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_VERSION_FILE="${REPO_ROOT}/.python-version"
ALPINE_VERSION_FILE="${REPO_ROOT}/.alpine-version"

if [[ ! -f "$PYTHON_VERSION_FILE" ]]; then
  echo "❌ Python version file not found: $PYTHON_VERSION_FILE" >&2
  exit 1
fi
if [[ ! -f "$ALPINE_VERSION_FILE" ]]; then
  echo "❌ Alpine version file not found: $ALPINE_VERSION_FILE" >&2
  exit 1
fi

PYTHON_VERSION="$(tr -d '[:space:]' < "$PYTHON_VERSION_FILE")"
ALPINE_VERSION="$(tr -d '[:space:]' < "$ALPINE_VERSION_FILE")"

if [[ ! "$PYTHON_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "❌ .python-version must be a patch pin X.Y.Z (got: '${PYTHON_VERSION:-<empty>}')" >&2
  exit 1
fi
if [[ ! "$ALPINE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "❌ .alpine-version must be a patch pin X.Y.Z (got: '${ALPINE_VERSION:-<empty>}')" >&2
  exit 1
fi

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
