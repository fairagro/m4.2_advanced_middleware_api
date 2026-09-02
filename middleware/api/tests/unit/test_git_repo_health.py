"""Unit tests for GitRepo health checks and validation."""

import http
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from middleware.api.arc_store.git_repo import GitRepo, GitRepoConfig


def test_validate_url_scheme_valid(tmp_path: Path) -> None:
    """Test valid URL schemes."""
    cache = tmp_path / "cache"
    GitRepoConfig(url="https://example.com/repo.git", group="group", cache_dir=cache)
    GitRepoConfig(url="file:///tmp/repo.git", group="group", cache_dir=cache)
    GitRepoConfig(url="http://example.com/repo.git", group="group", cache_dir=cache)


def test_validate_url_scheme_invalid(tmp_path: Path) -> None:
    """Test invalid URL schemes."""
    with pytest.raises(ValidationError) as excinfo:
        GitRepoConfig(url="ftp://example.com/repo.git", group="group", cache_dir=tmp_path / "cache")
    assert "Git URL must start with one of: ('https://', 'file://', 'http://')" in str(excinfo.value)


def test_validate_url_rejects_embedded_userinfo(tmp_path: Path) -> None:
    """Config URLs must not carry credentials; operators use the token field."""
    with pytest.raises(ValidationError) as excinfo:
        GitRepoConfig(
            url="https://oauth2:secret-token@example.com/repo.git",
            group="group",
            cache_dir=tmp_path / "cache",
        )
    assert "must not embed credentials in userinfo" in str(excinfo.value)


def test_check_health_file_scheme(tmp_path: Path) -> None:
    """Test health check for file:// scheme returns True regardless of path existence."""
    config = GitRepoConfig(url="file:///non/existent/path", group="group", cache_dir=tmp_path / "cache")
    repo = GitRepo(config)

    # Even if path doesn't exist, it should return True as per requirements
    assert repo.check_health() is True


@patch("urllib.request.urlopen")
def test_check_health_https_success(mock_urlopen: MagicMock, tmp_path: Path) -> None:
    """Test health check for https:// scheme success."""
    mock_response = MagicMock()
    mock_response.status = http.HTTPStatus.OK
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    config = GitRepoConfig(url="https://example.com", group="group", cache_dir=tmp_path / "cache")
    repo = GitRepo(config)

    assert repo.check_health() is True
    mock_urlopen.assert_called_once()


@patch("urllib.request.urlopen")
def test_check_health_https_failure_status(mock_urlopen: MagicMock, tmp_path: Path) -> None:
    """Test health check for https:// scheme failure (404)."""
    mock_response = MagicMock()
    mock_response.status = http.HTTPStatus.NOT_FOUND
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    config = GitRepoConfig(url="https://example.com", group="group", cache_dir=tmp_path / "cache")
    repo = GitRepo(config)

    assert repo.check_health() is False


@patch("urllib.request.urlopen")
def test_check_health_timeout(mock_urlopen: MagicMock, tmp_path: Path) -> None:
    """Test health check timeout handling."""
    mock_urlopen.side_effect = TimeoutError("timed out")

    config = GitRepoConfig(url="https://example.com", group="group", cache_dir=tmp_path / "cache")
    repo = GitRepo(config)

    assert repo.check_health() is False
