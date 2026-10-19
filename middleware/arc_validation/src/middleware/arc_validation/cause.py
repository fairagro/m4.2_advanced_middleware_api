"""Short failure excerpts from ``arc-export`` / ARCtrl logs."""

from __future__ import annotations

import re

INTERNAL_ERROR_HEADER_RE = re.compile(r"^Internal Error:\s*$", re.IGNORECASE)
CAUSE_HINT_RE = re.compile(
    r"(?i)(?:\berror\b|\bexception\b|\bfatal\b|\bfailed\b|\bmust have\b|"
    r"\binvalid\b|\bmissing\b|\bnot found\b|\bunable to\b|\bcannot\b)"
)
UNKNOWN_CAUSE = "(no usable log lines)"
EXCERPT_MAX_CHARS = 240
INTERNAL_ERROR_MAX_FOLLOW_LINES = 3


def _truncate_excerpt(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= EXCERPT_MAX_CHARS:
        return cleaned
    return f"{cleaned[: EXCERPT_MAX_CHARS - 1]}…"


def _extract_after_internal_error(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if not INTERNAL_ERROR_HEADER_RE.fullmatch(line):
            continue
        collected: list[str] = []
        for follower in lines[index + 1 :]:
            if not follower or follower.startswith("$"):
                break
            collected.append(follower)
            if len(collected) >= INTERNAL_ERROR_MAX_FOLLOW_LINES:
                break
        if collected:
            return " | ".join(collected)
    return None


def extract_cause_excerpt(*, stdout: str = "", stderr: str = "", fallback: str = "") -> str:
    """Prefer ``Internal Error:`` followers, then error-like lines, then fallback."""
    combined = "\n".join(part for part in (stderr, stdout, fallback) if part)
    if not combined.strip():
        return UNKNOWN_CAUSE

    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    internal = _extract_after_internal_error(lines)
    if internal:
        return _truncate_excerpt(internal)

    for line in reversed(lines):
        if CAUSE_HINT_RE.search(line):
            return _truncate_excerpt(line)

    if fallback.strip():
        return _truncate_excerpt(fallback)
    return _truncate_excerpt(lines[-1]) if lines else UNKNOWN_CAUSE
