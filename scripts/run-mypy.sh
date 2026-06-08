#!/bin/bash
# Run mypy on all workspace packages
# This script reads the mypy_path from pyproject.toml and converts it to package names

set -e

cd "$(dirname "$0")/.."

# Run mypy on each package using -p flag
# Package names are derived from the directory structure: middleware/*/src -> middleware.*
uv run mypy \
    -p middleware.api \
    -p middleware.api_client \
    -p middleware.shared
