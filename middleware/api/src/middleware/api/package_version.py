"""Resolve the installed middleware-api PEP 440 package version."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

# package_version.py → …/src/middleware/api/; project root (pyproject.toml) is parents[3].
_PYPROJECT_PARENT_INDEX = 3
_FALLBACK_VERSION = "0.0.0"


def resolve_api_package_version() -> str:
    """Return the PEP 440 version for the ``api`` distribution.

    Prefers ``importlib.metadata``; falls back to the package ``pyproject.toml``
    ``project.version``, then ``0.0.0``.
    """
    try:
        return version("api")
    except PackageNotFoundError:
        try:
            import tomllib

            resolved = Path(__file__).resolve()
            if len(resolved.parents) <= _PYPROJECT_PARENT_INDEX:
                return _FALLBACK_VERSION
            pyproject_path = resolved.parents[_PYPROJECT_PARENT_INDEX] / "pyproject.toml"
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            return str(data["project"]["version"])
        except (FileNotFoundError, KeyError, TypeError, OSError, IndexError):
            return _FALLBACK_VERSION
