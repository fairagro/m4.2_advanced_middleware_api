"""Unit tests for remote repository providers.

This module provides tests for:
- FileSystemGitProvider: manages bare repositories in the local file system
- GitlabGitProvider: manages repositories on GitLab using the GitLab API
"""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock, patch

import git
import pytest
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError

from middleware.api.arc_store import ArcStoreError
from middleware.api.arc_store.remote_git_provider import (
    GITLAB_PROJECT_NAME_MAX_LEN,
    FileSystemGitProvider,
    GitlabGitProvider,
    GitProjectMetadata,
    RemoteGitProvider,
    apply_gitlab_project_metadata,
    build_gitlab_project_name,
    git_project_metadata_from_arc,
    normalize_gitlab_topic,
    sanitize_gitlab_project_name,
)

_TEST_GIT_METADATA = GitProjectMetadata(
    rdi="test-rdi",
    arc_id="abc123hash",
    identifier="test-arc",
    display_name="",
)


@pytest.fixture
def temp_remote_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for remote repositories."""
    remote_dir = tmp_path / "remotes"
    remote_dir.mkdir()
    return remote_dir


class TestFileSystemGitProvider:
    """Tests for FileSystemGitProvider."""

    @staticmethod
    def test_ensure_repo_exists_creates_bare_repo(temp_remote_dir: Path) -> None:
        """Test that ensure_repo_exists creates a bare repository if it does not exist."""
        provider = FileSystemGitProvider(base_url=f"file://{temp_remote_dir}", group="my-group")
        arc_id = "test-arc"

        provider.ensure_repo_exists(arc_id, _TEST_GIT_METADATA)

        expected_path = temp_remote_dir / "my-group" / f"{arc_id}.git"
        assert expected_path.exists()
        assert expected_path.is_dir()

        # Verify it's a bare repo
        repo = git.Repo(expected_path)
        assert repo.bare

    @staticmethod
    def test_get_repo_url(temp_remote_dir: Path) -> None:
        """Test URL construction."""
        provider = FileSystemGitProvider(base_url=f"file://{temp_remote_dir}", group="my-group")
        url = provider.get_repo_url("test-arc")
        assert url == f"file://{temp_remote_dir}/my-group/test-arc.git"

    @staticmethod
    def test_check_health() -> None:
        """Test health check."""
        provider = FileSystemGitProvider(base_url="file:///tmp", group="g")
        assert provider.check_health() is True

        provider = FileSystemGitProvider(base_url="http://invalid", group="g")
        assert provider.check_health() is False


class TestGitlabGitProvider:
    """Tests for GitlabGitProvider."""

    @staticmethod
    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_ensure_repo_exists_calls_gitlab_api(mock_gitlab_class: MagicMock) -> None:
        """Test that ensure_repo_exists calls the GitLab API."""
        NAMESPACE_ID = 123  # noqa: N806

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        mock_group = MagicMock()
        mock_group.full_path = "my-group-path"
        mock_group.id = NAMESPACE_ID
        mock_gl.groups.get.return_value = mock_group

        mock_gl.projects.get.side_effect = GitlabGetError("Not Found", response_code=HTTPStatus.NOT_FOUND)

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="my-group", token="secret")  # nosec
        arc_id = "test-arc"

        provider.ensure_repo_exists(arc_id, metadata=_TEST_GIT_METADATA)

        mock_gl.groups.get.assert_called_with("my-group")
        mock_gl.projects.get.assert_called_with("my-group-path/test-arc")
        mock_gl.projects.create.assert_called_once()
        args = mock_gl.projects.create.call_args[0][0]
        assert args["name"] == "test-arc"
        assert args["path"] == arc_id
        assert args["namespace_id"] == NAMESPACE_ID

    @staticmethod
    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_ensure_repo_exists_sets_gitlab_metadata(mock_gitlab_class: MagicMock) -> None:
        """Test that human-readable metadata is applied when creating a project."""
        NAMESPACE_ID = 123  # noqa: N806

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        mock_group = MagicMock()
        mock_group.full_path = "my-group-path"
        mock_group.id = NAMESPACE_ID
        mock_gl.groups.get.return_value = mock_group
        mock_gl.projects.get.side_effect = GitlabGetError("Not Found", response_code=HTTPStatus.NOT_FOUND)

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="my-group", token="secret")  # nosec
        metadata = GitProjectMetadata(
            rdi="rdi-1",
            arc_id="abc123hash",
            display_name="Arabidopsis thaliana cold acclimation",
            identifier="AthalianaColdStressSugar",
            description="Cold stress experiment",
        )

        provider.ensure_repo_exists("abc123hash", metadata=metadata)

        args = mock_gl.projects.create.call_args[0][0]
        assert args["name"] == "AthalianaColdStressSugar"
        assert args["path"] == "abc123hash"
        assert args["topics"] == ["rdi-1"]
        assert args["description"] == "Arabidopsis thaliana cold acclimation\nCold stress experiment"

    @staticmethod
    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_ensure_repo_exists_updates_existing_project_metadata(mock_gitlab_class: MagicMock) -> None:
        """Test that metadata is refreshed when the GitLab project already exists."""
        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        mock_group = MagicMock()
        mock_group.full_path = "my-group-path"
        mock_gl.groups.get.return_value = mock_group

        mock_project = MagicMock()
        mock_project.name = "old-hash-name"
        mock_project.description = "old description"
        mock_project.topics = ["existing"]
        mock_gl.projects.get.return_value = mock_project

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="my-group", token="secret")  # nosec
        metadata = GitProjectMetadata(
            rdi="rdi-2",
            arc_id="abc123hash",
            display_name="Readable title",
            identifier="dataset-42",
        )

        provider.ensure_repo_exists("abc123hash", metadata=metadata)

        mock_gl.projects.create.assert_not_called()
        assert mock_project.name == "dataset-42"
        assert mock_project.description == "Readable title"
        assert mock_project.topics == ["existing", "rdi-2"]
        mock_project.save.assert_called_once()

    @staticmethod
    def test_apply_gitlab_project_metadata_skips_save_when_gitlab_values_match() -> None:
        """GitLab API may return None for empty description/topics; treat as already in sync."""
        mock_project = MagicMock()
        mock_project.name = "dataset-42 (rdi-1)"
        mock_project.description = None
        mock_project.topics = ["rdi-1"]
        metadata = GitProjectMetadata(
            rdi="rdi-1",
            arc_id="abc123hash",
            identifier="dataset-42 (rdi-1)",
            display_name="",
            description="",
        )

        apply_gitlab_project_metadata(mock_project, "abc123hash", metadata)

        mock_project.save.assert_not_called()

    @staticmethod
    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_ensure_repo_exists_401(mock_gitlab_class: MagicMock) -> None:
        """Test that ensure_repo_exists handles 401 Unauthorized correctly."""
        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Simulate 401 on group retrieval
        err = GitlabAuthenticationError("401 Unauthorized", response_code=HTTPStatus.UNAUTHORIZED)
        mock_gl.groups.get.side_effect = err

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="my-group", token="invalid")  # nosec

        with pytest.raises(ArcStoreError, match="401 Unauthorized"):
            provider.ensure_repo_exists("some-arc", metadata=_TEST_GIT_METADATA)

    @staticmethod
    def test_get_repo_url() -> None:
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

    @staticmethod
    @patch("middleware.api.arc_store.remote_git_provider.gitlab.Gitlab")
    def test_check_health(mock_gitlab_class: MagicMock) -> None:
        """Test health check using auth() call."""
        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="g", token="t")  # nosec

        mock_gl.auth.return_value = True
        assert provider.check_health() is True

        mock_gl.auth.side_effect = GitlabAuthenticationError()
        assert provider.check_health() is False

    @staticmethod
    @patch("urllib.request.urlopen")
    def test_check_health_without_token(mock_urlopen: MagicMock) -> None:
        """Test reachability fallback when no GitLab token is configured."""
        mock_response = MagicMock()
        mock_response.status = HTTPStatus.OK
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        provider = GitlabGitProvider(url="https://gitlab.com", group_name="g", token=None)

        assert provider.check_health() is True
        mock_urlopen.assert_called_once_with("https://gitlab.com", timeout=5)


class TestRemoteGitProviderFactory:
    """Tests for RemoteGitProvider factory method."""

    @staticmethod
    def test_from_url_file() -> None:
        """Test factory with file URL."""
        provider = RemoteGitProvider.from_url("file:///tmp", "group")
        assert isinstance(provider, FileSystemGitProvider)

    @staticmethod
    def test_from_url_https_defaults_to_gitlab() -> None:
        """Test factory with HTTPS URL defaults to GitLab."""
        provider = RemoteGitProvider.from_url("https://git.something.com", "group")
        assert isinstance(provider, GitlabGitProvider)

    @staticmethod
    def test_from_url_http_defaults_to_gitlab() -> None:
        """Test factory with HTTP URL defaults to GitLab."""
        provider = RemoteGitProvider.from_url("http://localhost:8080", "group")
        assert isinstance(provider, GitlabGitProvider)

    @staticmethod
    def test_from_url_unknown_fails() -> None:
        """Test that unknown protocols fail."""
        with pytest.raises(ValueError, match="Could not determine git provider"):
            RemoteGitProvider.from_url("ftp://server.local", "group")


def test_git_project_metadata_from_arc() -> None:
    """git_project_metadata_from_arc derives display fields from the ARC object."""
    arc = MagicMock()
    arc.Identifier = "ARC-001"
    arc.Title = "My Study"
    arc.Description = "A test"

    metadata = git_project_metadata_from_arc(
        arc,
        rdi="my-rdi",
        arc_id="hash123",
    )

    assert metadata.rdi == "my-rdi"
    assert metadata.arc_id == "hash123"
    assert metadata.identifier == "ARC-001 (my-rdi)"
    assert metadata.display_name == "My Study"
    assert metadata.description == "A test"


def test_build_gitlab_project_name_appends_rdi() -> None:
    """GitLab project titles include RDI so names stay unique within a group."""
    assert build_gitlab_project_name("study-2024", "my-rdi") == "study-2024 (my-rdi)"


def test_build_gitlab_project_name_truncates_long_identifier() -> None:
    """Very long ARC identifiers are truncated before the RDI suffix is appended."""
    long_id = "x" * 300
    rdi = "rdi-1"
    result = build_gitlab_project_name(long_id, rdi)
    assert result.endswith(f" ({rdi})")
    assert len(result) <= GITLAB_PROJECT_NAME_MAX_LEN


def test_sanitize_gitlab_project_name_replaces_slashes() -> None:
    """Slashes in identifiers are replaced for GitLab project titles."""
    assert sanitize_gitlab_project_name("study/2024") == "study-2024"


def test_sanitize_gitlab_project_name_rejects_empty() -> None:
    """Whitespace-only identifiers cannot become GitLab project titles."""
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_gitlab_project_name("   ")


def test_git_project_metadata_rejects_empty_identifier() -> None:
    """git_project_metadata_from_arc requires a non-empty ARC identifier."""
    arc = MagicMock()
    arc.Identifier = "   "
    arc.Title = ""
    arc.Description = None

    with pytest.raises(ValueError, match="identifier is required"):
        git_project_metadata_from_arc(arc, rdi="my-rdi", arc_id="hash123")


def test_normalize_gitlab_topic_empty_rdi_alnum_fallback() -> None:
    """RDI names with only stripped characters yield no GitLab topic."""
    assert normalize_gitlab_topic("---") is None
    assert normalize_gitlab_topic("rdi-1") == "rdi-1"
