#!/usr/bin/env bash
# Unit + smoke checks for the HTTP /v3 OpenAPI gate (#651).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

uv run python - <<'PY'
import importlib.util
import json
from pathlib import Path

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

breaking = load("conventional_breaking", Path("scripts/conventional_breaking.py"))
assert breaking.BREAKING_SUBJECT.search("feat!: break the client")
assert breaking.BREAKING_SUBJECT.search("fix(api)!: remove field")
assert not breaking.BREAKING_SUBJECT.search("feat: additive only")
assert breaking.BREAKING_FOOTER.search("feat: x\n\nBREAKING CHANGE: removed path\n")
print("breaking-marker regexes ok")

export_mod = load("export_openapi_v3", Path("scripts/export_openapi_v3.py"))
filtered = export_mod.filter_v3_paths({
    "openapi": "3.1.0",
    "paths": {
        "/v2/arcs": {"get": {}},
        "/v3/harvests": {"post": {}},
        "/v3/health": {"get": {}},
    },
    "components": {"schemas": {"Keep": {"type": "object"}}},
})
assert set(filtered["paths"]) == {"/v3/harvests", "/v3/health"}, filtered["paths"]
assert "Keep" in filtered["components"]["schemas"]
print("filter_v3_paths ok")
PY

EXPORT_OUT="$(mktemp)"
cleanup_export() { rm -f "${EXPORT_OUT}"; }
trap cleanup_export EXIT
uv run python "${ROOT}/scripts/export_openapi_v3.py" --repo-root "${ROOT}" -o "${EXPORT_OUT}"
uv run python - <<PY
import json
from pathlib import Path
spec = json.loads(Path("${EXPORT_OUT}").read_text())
paths = spec["paths"]
assert paths, "expected /v3 paths"
assert all(p.startswith("/v3") for p in paths), paths
assert not any(p.startswith("/v2") for p in paths), paths
print(f"export smoke ok ({len(paths)} paths)")
PY

# Ensure oasdiff is available for the rest of the test.
if ! command -v oasdiff >/dev/null 2>&1; then
  ./scripts/install-oasdiff.sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi
oasdiff version 2>/dev/null || oasdiff --version

# Identical tip/base → no breaking.
IDENTICAL_STATUS=0
oasdiff breaking --fail-on ERR "${EXPORT_OUT}" "${EXPORT_OUT}" || IDENTICAL_STATUS=$?
test "${IDENTICAL_STATUS}" -eq 0
echo "oasdiff identical specs ok"

# Tip removes a /v3 path → breaking.
BROKEN="$(mktemp)"
uv run python - <<PY
import json
from pathlib import Path
spec = json.loads(Path("${EXPORT_OUT}").read_text())
paths = dict(spec["paths"])
# Drop one path to force a consumer-visible break.
drop = next(iter(paths))
del paths[drop]
spec["paths"] = paths
Path("${BROKEN}").write_text(json.dumps(spec))
print(f"dropped path {drop!r} for breaking fixture")
PY
BREAK_STATUS=0
oasdiff breaking --fail-on ERR "${EXPORT_OUT}" "${BROKEN}" || BREAK_STATUS=$?
test "${BREAK_STATUS}" -eq 1
echo "oasdiff path-removal breaking ok"
rm -f "${BROKEN}"

# Gate decision matrix (mock export + oasdiff): undeclared fail / declared pass / clean pass.
uv run python - <<'PY'
import importlib.util
from pathlib import Path

path = Path("scripts/check_openapi_v3.py")
spec = importlib.util.spec_from_file_location("check_openapi_v3", path)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

calls: dict[str, int] = {"export": 0}


def fake_export(*, repo_root, output, workspace):  # noqa: ANN001
    calls["export"] += 1
    output.write_text('{"openapi":"3.1.0","paths":{"/v3/x":{}}}')


mod._export_openapi = fake_export
mod._add_worktree = lambda **kwargs: None  # noqa: ARG005
mod._remove_worktree = lambda **kwargs: None  # noqa: ARG005
mod._which_oasdiff = lambda explicit: Path("/bin/true")  # noqa: ARG005
mod.resolve_base_ref = lambda explicit, cwd: "main"  # noqa: ARG005

mod.run_oasdiff_breaking = lambda **kwargs: 1  # noqa: ARG005
mod.branch_declares_breaking = lambda **kwargs: False  # noqa: ARG005
assert mod.main([]) == 1, "undeclared breaking must fail"

mod.branch_declares_breaking = lambda **kwargs: True  # noqa: ARG005
assert mod.main([]) == 0, "declared breaking must pass"

mod.run_oasdiff_breaking = lambda **kwargs: 0  # noqa: ARG005
mod.branch_declares_breaking = lambda **kwargs: False  # noqa: ARG005
assert mod.main([]) == 0, "non-breaking must pass"
assert calls["export"] >= 2
print("gate decision matrix ok")
PY

# Gate vs main on current tip (expect pass: no undeclared /v3 breaks).
./scripts/check-openapi-v3.sh --base main
echo "check-openapi-v3 vs main ok"
