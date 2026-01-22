"""Unit tests for remote repository managers.

This module provides tests for:
- FileSystemRemoteManager: manages bare repositories in the local file system
- GitlabRemoteManager: manages repositories on GitLab using the GitLab API
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import git
import pytest
from gitlab.exceptions import GitlabGetError

from middleware.api.arc_store.remote_repo_manager import (
    FileSystemRemoteManager,
    GitlabRemoteManager,
)


@pytest.fixture
def temp_remote_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for remote repositories.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory path provided by pytest.

    Returns
    -------
    pathlib.Path
        Path to the temporary remote directory.
    """
    remote_dir = tmp_path / "remotes"
    remote_dir.mkdir()
    return remote_dir


class TestFileSystemRemoteManager:
    """Tests for FileSystemRemoteManager.

    Tests the functionality of creating and managing bare repositories
    in the local file system.
    """

    def test_ensure_repo_exists_creates_bare_repo(self, temp_remote_dir: Path) -> None:
        """Test that ensure_repo_exists creates a bare repository if it does not exist.

        Parameters
        ----------
        temp_remote_dir : pathlib.Path
            Temporary directory for remote repositories.
        """
        manager = FileSystemRemoteManager(base_url=f"file://{temp_remote_dir}", group="my-group")
        arc_id = "test-arc"

        manager.ensure_repo_exists(arc_id)

        expected_path = temp_remote_dir / "my-group" / f"{arc_id}.git"
        assert expected_path.exists()
        assert expected_path.is_dir()

        # Verify it's a bare repo
        repo = git.Repo(expected_path)
        assert repo.bare

    def test_ensure_repo_exists_already_exists(self, temp_remote_dir: Path) -> None:
        """Test that ensure_repo_exists does not fail if the repository already exists.

        Parameters
        ----------
        temp_remote_dir : pathlib.Path
            Temporary directory for remote repositories.
        """
        manager = FileSystemRemoteManager(base_url=f"file://{temp_remote_dir}", group="my-group")
        arc_id = "test-arc"
        repo_path = temp_remote_dir / "my-group" / f"{arc_id}.git"
        repo_path.mkdir(parents=True)

        # Should not raise or fail
        manager.ensure_repo_exists(arc_id)
        assert repo_path.exists()


class TestGitlabRemoteManager:
    """Tests for GitlabRemoteManager.

    Tests the functionality of creating and managing repositories
    on GitLab using the GitLab API.
    """

    @patch("middleware.api.arc_store.remote_repo_manager.gitlab.Gitlab")
    def test_ensure_repo_exists_calls_gitlab_api(self, mock_gitlab_class: MagicMock) -> None:
        """Test that ensure_repo_exists calls the GitLab API to create a project if it does not exist.

        Parameters
        ----------
        mock_gitlab_class : MagicMock
            Mocked Gitlab class.
        """
        NAMESPACE_ID = 123  # noqa: N806

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        mock_group = MagicMock()
        mock_group.full_path = "my-group-path"
        mock_group.id = NAMESPACE_ID
        mock_gl.groups.get.return_value = mock_group

        # Simulate project not found first, then created

        mock_gl.projects.get.side_effect = GitlabGetError("Not Found", response_code=404)

        manager = GitlabRemoteManager(url="https://gitlab.com", group_name="my-group", token="secret")
        arc_id = "test-arc"

        manager.ensure_repo_exists(arc_id)

        mock_gl.groups.get.assert_called_with("my-group")
        mock_gl.projects.get.assert_called_with("my-group-path/test-arc")
        mock_gl.projects.create.assert_called_once()
        args = mock_gl.projects.create.call_args[0][0]
        assert args["name"] == arc_id
        assert args["namespace_id"] == NAMESPACE_ID
