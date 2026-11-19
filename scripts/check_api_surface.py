#!/usr/bin/env python3
"""Fail undeclared public Python API breaks (griffe) vs a Git base ref (#570).

Exit 0 when the allowlisted surface has no breaking changes vs BASE, or when
breaking changes are declared on main..HEAD via Conventional Commits
(`type!:` / `type(scope)!:` or a `BREAKING CHANGE:` footer).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from griffe import find_breaking_changes, load, load_git


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
# Re-export for scripts/tests/test_check_api_surface.sh
_BREAKING_SUBJECT = _conventional_breaking.BREAKING_SUBJECT
_BREAKING_FOOTER = _conventional_breaking.BREAKING_FOOTER
branch_declares_breaking = _conventional_breaking.branch_declares_breaking
resolve_base_ref = _conventional_breaking.resolve_base_ref

_DEFAULT_ALLOWLIST = Path("api-surface-allowlist.yaml")


def _load_allowlist(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path}: expected a mapping with 'packages'"
        raise SystemExit(msg)
    packages = data.get("packages")
    if not isinstance(packages, list) or not packages:
        msg = f"{path}: 'packages' must be a non-empty list"
        raise SystemExit(msg)
    return packages


def _package_breakages(
    name: str,
    search_paths: Sequence[str],
    *,
    base: str,
    cwd: Path,
) -> list[Any]:
    # load_git joins each path onto a temporary worktree; absolute paths drop that
    # prefix on POSIX and would load HEAD instead of ``base``.
    relative_paths = list(search_paths)
    head_paths = [str(cwd / p) for p in relative_paths]
    try:
        old = load_git(name, ref=base, search_paths=relative_paths, repo=str(cwd))
    except Exception as exc:  # noqa: BLE001 — surface load errors as gate failures
        print(f"error: failed to load {name!r} at {base}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    try:
        new = load(name, search_paths=head_paths)
    except Exception as exc:  # noqa: BLE001
        print(f"error: failed to load {name!r} at HEAD: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    return list(find_breaking_changes(old, new))


def collect_breakages(
    packages: Iterable[dict[str, Any]],
    *,
    base: str,
    cwd: Path,
) -> list[tuple[str, Any]]:
    """Collect griffe breaking changes for each allowlisted package vs base."""
    found: list[tuple[str, Any]] = []
    for entry in packages:
        name = entry.get("name")
        search_paths = entry.get("search_paths")
        if not isinstance(name, str) or not name:
            raise SystemExit("allowlist entry missing string 'name'")
        if not isinstance(search_paths, list) or not all(isinstance(p, str) for p in search_paths):
            raise SystemExit(f"{name}: 'search_paths' must be a list of strings")
        for breakage in _package_breakages(name, search_paths, base=base, cwd=cwd):
            found.append((name, breakage))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """Run the API surface gate; return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=_DEFAULT_ALLOWLIST,
        help=f"Allowlist YAML (default: {_DEFAULT_ALLOWLIST})",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Git ref to diff against (default: origin/main, else main)",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Repository root (default: cwd)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    cwd = (args.cwd or Path.cwd()).resolve()
    allowlist_path = args.allowlist if args.allowlist.is_absolute() else cwd / args.allowlist
    if not allowlist_path.is_file():
        print(f"error: allowlist not found: {allowlist_path}", file=sys.stderr)
        return 2

    base = resolve_base_ref(args.base, cwd=cwd)
    packages = _load_allowlist(allowlist_path)
    breakages = collect_breakages(packages, base=base, cwd=cwd)
    if not breakages:
        print(f"API surface vs {base}: no breaking changes.")
        return 0

    print(f"API surface vs {base}: {len(breakages)} breaking change(s):")
    for package_name, breakage in breakages:
        print(f"  - [{package_name}] {breakage}")

    if branch_declares_breaking(base=base, cwd=cwd):
        print("Breaking Conventional Commit marker found on branch; allowing merge.")
        return 0

    print(
        "error: undeclared breaking API change(s). "
        "Add a Conventional Commit with `type!:` or a `BREAKING CHANGE:` footer, "
        "or revert the surface break.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
