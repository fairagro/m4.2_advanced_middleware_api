#!/usr/bin/env python3
"""Fail undeclared public Python API breaks (griffe) vs a Git base ref (#570).

Exit 0 when the allowlisted surface has no breaking changes vs BASE, or when
breaking changes are declared on main..HEAD via Conventional Commits
(`type!:` / `type(scope)!:` or a `BREAKING CHANGE:` footer).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import yaml
from griffe import find_breaking_changes, load, load_git

_BREAKING_SUBJECT = re.compile(r"^[a-z]+(?:\([^)]*\))?!:", re.MULTILINE)
_BREAKING_FOOTER = re.compile(r"^BREAKING CHANGE:", re.MULTILINE)
_DEFAULT_ALLOWLIST = Path("api-surface-allowlist.yaml")


def _git_output(args: Sequence[str], *, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def resolve_base_ref(explicit: str | None, *, cwd: Path) -> str:
    """Return an explicit base ref or the first available of origin/main, main."""
    if explicit:
        return explicit
    for candidate in ("origin/main", "main"):
        try:
            _git_output(["rev-parse", "--verify", candidate], cwd=cwd)
        except subprocess.CalledProcessError:
            continue
        return candidate
    msg = "Could not resolve base ref (tried origin/main, main); pass --base"
    raise SystemExit(msg)


def branch_declares_breaking(*, base: str, cwd: Path) -> bool:
    """Return whether any commit on base..HEAD declares a Conventional Commits break."""
    try:
        log = _git_output(["log", f"{base}..HEAD", "--format=%B%x00"], cwd=cwd)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"git log {base}..HEAD failed: {exc}") from exc
    for message in log.split("\0"):
        text = message.strip()
        if not text:
            continue
        if _BREAKING_SUBJECT.search(text) or _BREAKING_FOOTER.search(text):
            return True
    return False


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
    paths = [str(cwd / p) for p in search_paths]
    try:
        old = load_git(name, ref=base, search_paths=paths, repo=str(cwd))
    except Exception as exc:  # noqa: BLE001 — surface load errors as gate failures
        print(f"error: failed to load {name!r} at {base}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    try:
        new = load(name, search_paths=paths)
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
