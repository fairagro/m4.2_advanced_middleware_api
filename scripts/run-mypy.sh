#!/bin/bash
# Run mypy on all workspace packages
# This script runs mypy on the specified workspace packages.

set -e

cd "$(dirname "$0")/.."

# Run mypy on each package using -p flag
# Package names are derived from the directory structure: middleware/*/src -> middleware.*
uv run mypy \
    -p middleware.api \
    -p middleware.api_client \
    -p middleware.shared
