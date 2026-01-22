"""Unit tests for remote repository providers.

This module provides tests for:
- FileSystemGitProvider: manages bare repositories in the local file system
- GitlabGitProvider: manages repositories on GitLab using the GitLab API
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import git
import pytest
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError

from middleware.api.arc_store import ArcStoreError
from middleware.api.arc_store.remote_git_provider import (
    FileSystemGitProvider,
    GitlabGitProvider,
    RemoteGitProvider,
)


@pytest.fixture
def temp_remote_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for remote repositories."""
    remote_dir = tmp_path / "remotes"
    remote_dir.mkdir()
    return remote_dir


class TestFileSystemGitProvider:
    """Tests for FileSystemGitProvider."""

    def test_ensure_repo_exists_creates_bare_repo(self, temp_remote_dir: Path) -> None:
        """Test that ensure_repo_exists creates a bare repository if it does not exist."""
        provider = FileSystemGitProvider(base_url=f"file://{temp_remote_dir}", group="my-group")
        arc_id = "test-arc"

        provider.ensure_repo_exists(arc_id)

        expected_path = temp_remote_dir / "my-group" / f"{arc_id}.git"
        assert expected_path.exists()
        assert expected_path.is_dir()

        # Verify it's a bare repo
        repo = git.Repo(expected_path)
        assert repo.bare

    def test_get_repo_url(self, temp_remote_dir: Path) -> None:
        """Test URL construction."""
        provider = FileSystemGitProvider(base_url=f"file://{temp_remote_dir}", group="my-group")
        url = provider.get_repo_url("test-arc")
        assert url == f"file://{temp_remote_dir}/my-group/test-arc.git"

    def test_check_health(self) -> None:
        """Test health check."""
        provider = FileSystemGitProvider(base_url="file:///tmp", group="g")
        assert provider.check_health() is True

        provider = FileSystemGitProvider(base_url="http://invalid", group="g")
        assert provider.check_health() is False


class TestGitlabGitProvider:
    """Tests for GitlabGitProvider."""

    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_ensure_repo_exists_calls_gitlab_api(self, mock_gitlab_class: MagicMock) -> None:
        """Test that ensure_repo_exists calls the GitLab API."""
        NAMESPACE_ID = 123  # noqa: N806

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        mock_group = MagicMock()
        mock_group.full_path = "my-group-path"
        mock_group.id = NAMESPACE_ID
        mock_gl.groups.get.return_value = mock_group

        mock_gl.projects.get.side_effect = GitlabGetError("Not Found", response_code=404)

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="my-group", token="secret")  # nosec
        arc_id = "test-arc"

        provider.ensure_repo_exists(arc_id)

        mock_gl.groups.get.assert_called_with("my-group")
        mock_gl.projects.get.assert_called_with("my-group-path/test-arc")
        mock_gl.projects.create.assert_called_once()
        args = mock_gl.projects.create.call_args[0][0]
        assert args["name"] == arc_id
        assert args["namespace_id"] == NAMESPACE_ID

    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_ensure_repo_exists_401(self, mock_gitlab_class: MagicMock) -> None:
        """Test that ensure_repo_exists handles 401 Unauthorized correctly."""
        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Simulate 401 on group retrieval
        err = GitlabAuthenticationError("401 Unauthorized", response_code=401)
        mock_gl.groups.get.side_effect = err

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="my-group", token="invalid")  # nosec

        with pytest.raises(ArcStoreError, match="401 Unauthorized"):
            provider.ensure_repo_exists("some-arc")

    def test_get_repo_url(self) -> None:
        """Test URL construction with and without auth."""
        url = "https://gitlab.com"
        token = "secret-token"  # nosec
        provider = GitlabGitProvider(url=url, group_name="my-group", token=token)

        # Authenticated
        auth_url = provider.get_repo_url("arc123", authenticated=True)
        assert auth_url == "https://oauth2:secret-token@gitlab.com/my-group/arc123.git"

        # Not authenticated
        plain_url = provider.get_repo_url("arc123", authenticated=False)
        assert plain_url == "https://gitlab.com/my-group/arc123.git"

    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_check_health(self, mock_gitlab_class: MagicMock) -> None:
        """Test health check using auth() call."""
        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="g", token="t")  # nosec

        mock_gl.auth.return_value = True
        assert provider.check_health() is True

        mock_gl.auth.side_effect = GitlabAuthenticationError()
        assert provider.check_health() is False


class TestRemoteGitProviderFactory:
    """Tests for RemoteGitProvider factory method."""

    def test_from_url_file(self) -> None:
        """Test factory with file URL."""
        provider = RemoteGitProvider.from_url("file:///tmp", "group")
        assert isinstance(provider, FileSystemGitProvider)

    def test_from_url_https_defaults_to_gitlab(self) -> None:
        """Test factory with HTTPS URL defaults to GitLab."""
        provider = RemoteGitProvider.from_url("https://git.something.com", "group")
        assert isinstance(provider, GitlabGitProvider)

    def test_from_url_http_defaults_to_gitlab(self) -> None:
        """Test factory with HTTP URL defaults to GitLab."""
        provider = RemoteGitProvider.from_url("http://localhost:8080", "group")
        assert isinstance(provider, GitlabGitProvider)

    def test_from_url_unknown_fails(self) -> None:
        """Test that unknown protocols fail."""
        with pytest.raises(ValueError, match="Could not determine git provider"):
            RemoteGitProvider.from_url("ftp://server.local", "group")
