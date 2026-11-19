#!/usr/bin/env python3
"""Fail undeclared HTTP /v3 OpenAPI breaks (oasdiff) vs a Git base ref (#651).

Exit 0 when the filtered /v3 OpenAPI has no breaking changes vs BASE, or when
breaking changes are declared on main..HEAD via Conventional Commits
(`type!:` / `type(scope)!:` or a `BREAKING CHANGE:` footer).
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType


def _load_conventional_breaking() -> ModuleType:
    """Load sibling ``conventional_breaking.py`` (scripts/ is not a package)."""
    path = Path(__file__).resolve().parent / "conventional_breaking.py"
    spec = importlib.util.spec_from_file_location("conventional_breaking", path)
    if spec is None or spec.loader is None:
        msg = f"cannot load {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["conventional_breaking"] = module
    spec.loader.exec_module(module)
    return module


_conventional_breaking = _load_conventional_breaking()
branch_declares_breaking = _conventional_breaking.branch_declares_breaking
git_output = _conventional_breaking.git_output
resolve_base_ref = _conventional_breaking.resolve_base_ref

_SCRIPTS_DIR = Path(__file__).resolve().parent

_EXPORT_SCRIPT = _SCRIPTS_DIR / "export_openapi_v3.py"
_DEFAULT_OASDIFF_VERSION = "1.39.0"


def _which_oasdiff(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise SystemExit(f"oasdiff not found: {explicit}")
        return explicit
    found = shutil.which("oasdiff")
    if found:
        return Path(found)
    raise SystemExit(
        "oasdiff not on PATH; install via ./scripts/install-oasdiff.sh "
        f"(pin {_DEFAULT_OASDIFF_VERSION}) or pass --oasdiff",
    )


def _export_openapi(*, repo_root: Path, output: Path, workspace: Path) -> None:
    cmd = [
        "uv",
        "run",
        "python",
        str(_EXPORT_SCRIPT),
        "--repo-root",
        str(repo_root),
        "-o",
        str(output),
    ]
    env = os.environ.copy()
    # Ensure scripts/ is importable if export grows shared helpers.
    env["PYTHONPATH"] = (
        f"{_SCRIPTS_DIR}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(_SCRIPTS_DIR)
    )
    try:
        subprocess.check_call(cmd, cwd=workspace, env=env)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"OpenAPI export failed for {repo_root}: {exc}") from exc


def _add_worktree(*, cwd: Path, base: str, path: Path) -> None:
    try:
        git_output(["worktree", "add", "--detach", str(path), base], cwd=cwd)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"git worktree add failed for {base}: {exc}") from exc


def _remove_worktree(*, cwd: Path, path: Path) -> None:
    try:
        git_output(["worktree", "remove", "--force", str(path)], cwd=cwd)
    except subprocess.CalledProcessError:
        # Best-effort cleanup; temp dir removal still runs.
        shutil.rmtree(path, ignore_errors=True)


def run_oasdiff_breaking(
    *,
    oasdiff: Path,
    base_spec: Path,
    tip_spec: Path,
) -> int:
    """Return oasdiff exit code (0 = no breaking, 1 = breaking found)."""
    # oasdiff ≥1.39 exits 0 unless --fail-on is set; ERR matches breaking severity.
    result = subprocess.run(
        [str(oasdiff), "breaking", "--fail-on", "ERR", str(base_spec), str(tip_spec)],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode not in {0, 1}:
        raise SystemExit(f"oasdiff failed with unexpected exit code {result.returncode}")
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Run the /v3 OpenAPI gate; return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=None,
        help="Git ref to diff against (default: origin/main, else main)",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Repository root / tip tree (default: cwd)",
    )
    parser.add_argument(
        "--oasdiff",
        type=Path,
        default=None,
        help="Path to oasdiff binary (default: PATH)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    cwd = (args.cwd or Path.cwd()).resolve()
    if not _EXPORT_SCRIPT.is_file():
        print(f"error: missing export script {_EXPORT_SCRIPT}", file=sys.stderr)
        return 2

    oasdiff = _which_oasdiff(args.oasdiff)
    base = resolve_base_ref(args.base, cwd=cwd)

    with tempfile.TemporaryDirectory(prefix="openapi-v3-gate-") as tmp:
        tmp_path = Path(tmp)
        tip_spec = tmp_path / "tip.openapi.json"
        base_spec = tmp_path / "base.openapi.json"
        worktree = tmp_path / "base-worktree"

        _export_openapi(repo_root=cwd, output=tip_spec, workspace=cwd)

        _add_worktree(cwd=cwd, base=base, path=worktree)
        try:
            _export_openapi(repo_root=worktree.resolve(), output=base_spec, workspace=cwd)
        finally:
            _remove_worktree(cwd=cwd, path=worktree)

        breaking_code = run_oasdiff_breaking(oasdiff=oasdiff, base_spec=base_spec, tip_spec=tip_spec)

    if breaking_code == 0:
        print(f"OpenAPI /v3 vs {base}: no breaking changes.")
        return 0

    print(f"OpenAPI /v3 vs {base}: breaking change(s) reported by oasdiff.")
    if branch_declares_breaking(base=base, cwd=cwd):
        print("Breaking Conventional Commit marker found on branch; allowing merge.")
        return 0

    print(
        "error: undeclared breaking /v3 OpenAPI change(s). "
        "Add a Conventional Commit with `type!:` or a `BREAKING CHANGE:` footer, "
        "or revert the contract break.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
