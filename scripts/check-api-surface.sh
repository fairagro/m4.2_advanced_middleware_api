#!/usr/bin/env bash
# Public Python API surface gate (#570). See docs/quality.md.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
exec uv run python "${ROOT}/scripts/check_api_surface.py" "$@"
