"""Unit tests for GitRepo health checks and validation."""

import http
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from middleware.api.arc_store.git_repo import GitRepo, GitRepoConfig


def test_validate_url_scheme_valid() -> None:
    """Test valid URL schemes."""
    GitRepoConfig(url="https://example.com/repo.git", group="group", cache_dir=Path("/tmp"))  # nosec B108
    GitRepoConfig(url="file:///tmp/repo.git", group="group", cache_dir=Path("/tmp"))  # nosec B108
    GitRepoConfig(url="http://example.com/repo.git", group="group", cache_dir=Path("/tmp"))  # nosec B108


def test_validate_url_scheme_invalid() -> None:
    """Test invalid URL schemes."""
    with pytest.raises(ValidationError) as excinfo:
        GitRepoConfig(url="ftp://example.com/repo.git", group="group", cache_dir=Path("/tmp"))  # nosec B108
    assert "Git URL must start with one of: ('https://', 'file://', 'http://')" in str(excinfo.value)


def test_check_health_file_scheme() -> None:
    """Test health check for file:// scheme returns True regardless of path existence."""
    config = GitRepoConfig(url="file:///non/existent/path", group="group", cache_dir=Path("/tmp"))  # nosec B108
    repo = GitRepo(config)

    # Even if path doesn't exist, it should return True as per requirements
    assert repo.check_health() is True


@patch("urllib.request.urlopen")
def test_check_health_https_success(mock_urlopen: MagicMock) -> None:
    """Test health check for https:// scheme success."""
    mock_response = MagicMock()
    mock_response.status = http.HTTPStatus.OK
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    config = GitRepoConfig(url="https://example.com", group="group", cache_dir=Path("/tmp"))  # nosec B108
    repo = GitRepo(config)

    assert repo.check_health() is True
    mock_urlopen.assert_called_once()


@patch("urllib.request.urlopen")
def test_check_health_https_failure_status(mock_urlopen: MagicMock) -> None:
    """Test health check for https:// scheme failure (404)."""
    mock_response = MagicMock()
    mock_response.status = http.HTTPStatus.NOT_FOUND
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    config = GitRepoConfig(url="https://example.com", group="group", cache_dir=Path("/tmp"))  # nosec B108
    repo = GitRepo(config)

    assert repo.check_health() is False


@patch("urllib.request.urlopen")
def test_check_health_timeout(mock_urlopen: MagicMock) -> None:
    """Test health check timeout handling."""
    mock_urlopen.side_effect = TimeoutError("timed out")

    config = GitRepoConfig(url="https://example.com", group="group", cache_dir=Path("/tmp"))  # nosec B108
    repo = GitRepo(config)

    assert repo.check_health() is False
