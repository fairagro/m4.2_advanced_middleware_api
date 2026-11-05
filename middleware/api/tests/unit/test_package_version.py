"""Unit tests for package version resolution."""

from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from middleware.api import package_version


def test_resolve_api_package_version_returns_non_empty_string() -> None:
    """Resolver returns a non-empty string in the test environment."""
    resolved = package_version.resolve_api_package_version()
    assert isinstance(resolved, str)
    assert resolved


def test_resolve_api_package_version_falls_back_to_pyproject(tmp_path: Path) -> None:
    """When the distribution is missing, read project.version from pyproject.toml."""
    project_root = tmp_path / "middleware" / "api"
    package_dir = project_root / "src" / "middleware" / "api"
    package_dir.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    fake_module = package_dir / "package_version.py"
    fake_module.write_text("# stub\n", encoding="utf-8")

    with (
        patch.object(package_version, "version", side_effect=PackageNotFoundError("api")),
        patch.object(package_version, "__file__", str(fake_module)),
    ):
        assert package_version.resolve_api_package_version() == "1.2.3"


def test_resolve_api_package_version_falls_back_to_zero() -> None:
    """When metadata and pyproject are unavailable, return 0.0.0."""
    with (
        patch.object(package_version, "version", side_effect=PackageNotFoundError("api")),
        patch.object(package_version, "__file__", "/nonexistent/package_version.py"),
    ):
        assert package_version.resolve_api_package_version() == "0.0.0"
