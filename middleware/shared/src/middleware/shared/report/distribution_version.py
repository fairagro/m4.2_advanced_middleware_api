"""Helpers for reading installed Python distribution versions."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def read_distribution_version(distribution_name: str) -> str | None:
    """Return the installed PEP 440 version for ``distribution_name``, or ``None``.

    Returns ``None`` when the distribution is not installed (no metadata). Does not
    fall back to reading ``pyproject.toml`` from disk.
    """
    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None
