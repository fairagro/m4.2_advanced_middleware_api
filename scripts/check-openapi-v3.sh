#!/usr/bin/env bash
# HTTP /v3 OpenAPI breaking-diff gate (#651). See docs/openapi-v3-check.md.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec uv run python "${ROOT}/scripts/check_openapi_v3.py" "$@"
