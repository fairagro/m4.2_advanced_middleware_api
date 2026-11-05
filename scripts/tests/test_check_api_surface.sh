#!/usr/bin/env bash
# Unit checks for Conventional Commit breaking-marker detection (#570).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

uv run python - <<'PY'
import importlib.util
from pathlib import Path

path = Path("scripts/check_api_surface.py")
spec = importlib.util.spec_from_file_location("check_api_surface", path)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert mod._BREAKING_SUBJECT.search("feat!: break the client")
assert mod._BREAKING_SUBJECT.search("fix(api)!: remove field")
assert not mod._BREAKING_SUBJECT.search("feat: additive only")
assert mod._BREAKING_FOOTER.search("feat: x\n\nBREAKING CHANGE: removed ApiClient.foo\n")
assert not mod._BREAKING_FOOTER.search("feat: x\n\nSee CHANGELOG\n")
print("breaking-marker regexes ok")
PY

# Live gate against current main (expect no undeclared breaks on a clean tip).
./scripts/check-api-surface.sh --base main
echo "check-api-surface vs main ok"
