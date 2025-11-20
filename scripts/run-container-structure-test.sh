#!/bin/bash
set -e

echo "🔧 Building Docker image for container structure test..."
docker build -f docker/Dockerfile.api -t fairagro-advanced-middleware-api:test .

echo "🔍 Running Container Structure Test..."
container-structure-test test \
    --image fairagro-advanced-middleware-api:test \
    --config docker/container-structure-tests/api.yaml
