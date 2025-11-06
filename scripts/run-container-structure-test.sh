#!/bin/bash
set -e

echo "🔧 Building Docker image for container structure test..."
docker build . -t fairagro-advanced-middleware-api:test

echo "🔍 Running Container Structure Test..."
container-structure-test test \
    --image fairagro-advanced-middleware-api:test \
    --config tests/container-structure-test.yaml
