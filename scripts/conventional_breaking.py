"""Conventional Commits breaking-marker helpers for surface gates (#570 / #651)."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

BREAKING_SUBJECT = re.compile(r"^[a-z]+(?:\([^)]*\))?!:", re.MULTILINE)
BREAKING_FOOTER = re.compile(r"^BREAKING CHANGE:", re.MULTILINE)


def git_output(args: Sequence[str], *, cwd: Path) -> str:
    """Return stdout from a git invocation, raising CalledProcessError on failure."""
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def resolve_base_ref(explicit: str | None, *, cwd: Path) -> str:
    """Return an explicit base ref or the first available of origin/main, main."""
    if explicit:
        return explicit
    for candidate in ("origin/main", "main"):
        try:
            git_output(["rev-parse", "--verify", candidate], cwd=cwd)
        except subprocess.CalledProcessError:
            continue
        return candidate
    msg = "Could not resolve base ref (tried origin/main, main); pass --base"
    raise SystemExit(msg)


def branch_declares_breaking(*, base: str, cwd: Path) -> bool:
    """Return whether any commit on base..HEAD declares a Conventional Commits break."""
    try:
        log = git_output(["log", f"{base}..HEAD", "--format=%B%x00"], cwd=cwd)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"git log {base}..HEAD failed: {exc}") from exc
    for message in log.split("\0"):
        text = message.strip()
        if not text:
            continue
        if BREAKING_SUBJECT.search(text) or BREAKING_FOOTER.search(text):
            return True
    return False
