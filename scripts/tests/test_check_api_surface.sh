#!/usr/bin/env bash
# Unit + fixture checks for the API surface gate (#570).
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

# load_git must receive repo-relative search_paths (absolute paths drop the worktree).
captured: dict[str, object] = {}


def fake_load_git(name, *, ref, search_paths, repo):  # noqa: ANN001
    captured["load_git_search_paths"] = list(search_paths)
    return object()


def fake_load(name, *, search_paths):  # noqa: ANN001
    captured["load_search_paths"] = list(search_paths)
    return object()


mod.load_git = fake_load_git
mod.load = fake_load
mod.find_breaking_changes = lambda old, new: []  # noqa: ARG005
cwd = Path("/tmp/api-surface-fixture-cwd")
mod._package_breakages(
    "demo.pkg",
    ["src"],
    base="main",
    cwd=cwd,
)
assert captured["load_git_search_paths"] == ["src"], captured
assert captured["load_search_paths"] == [str(cwd / "src")], captured
print("load_git relative search_paths ok")
PY

# Fixture repo: removing a public function is an undeclared break → exit 1.
FIXTURE="$(mktemp -d)"
cleanup() { rm -rf "${FIXTURE}"; }
trap cleanup EXIT

git -C "${FIXTURE}" init -q
git -C "${FIXTURE}" config user.email "test@example.com"
git -C "${FIXTURE}" config user.name "API Surface Test"
mkdir -p "${FIXTURE}/src/demo_pkg"
cat >"${FIXTURE}/src/demo_pkg/__init__.py" <<'PY'
"""Demo package."""

def keep() -> None:
    """Stable public API."""


def doomed() -> None:
    """Removed on HEAD to force a breaking change."""
PY
git -C "${FIXTURE}" add src
git -C "${FIXTURE}" commit -qm "feat: baseline surface"
BASE_SHA="$(git -C "${FIXTURE}" rev-parse HEAD)"

cat >"${FIXTURE}/src/demo_pkg/__init__.py" <<'PY'
"""Demo package."""

def keep() -> None:
    """Stable public API."""
PY
git -C "${FIXTURE}" add src
git -C "${FIXTURE}" commit -qm "feat: remove doomed without breaking marker"

cat >"${FIXTURE}/api-surface-allowlist.yaml" <<'YAML'
packages:
  - name: demo_pkg
    search_paths:
      - src
YAML

set +e
uv run python "${ROOT}/scripts/check_api_surface.py" \
  --cwd "${FIXTURE}" \
  --base "${BASE_SHA}" \
  --allowlist "${FIXTURE}/api-surface-allowlist.yaml"
STATUS=$?
set -e
test "${STATUS}" -eq 1
echo "undeclared break fails ok"

# Same tip with a breaking Conventional Commit → exit 0.
git -C "${FIXTURE}" commit --allow-empty -qm "feat!: declare the surface break"
uv run python "${ROOT}/scripts/check_api_surface.py" \
  --cwd "${FIXTURE}" \
  --base "${BASE_SHA}" \
  --allowlist "${FIXTURE}/api-surface-allowlist.yaml"
echo "declared break passes ok"

# Live gate against current main (expect no undeclared breaks on a clean tip).
./scripts/check-api-surface.sh --base main
echo "check-api-surface vs main ok"
