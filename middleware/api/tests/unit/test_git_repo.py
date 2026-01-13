"""Unit tests for the GitRepo persistence layer (git_repo.py)."""
# pylint: disable=protected-access

import asyncio
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from git.exc import GitCommandError
from pydantic import SecretStr

from middleware.api.arc_store.git_repo import GitContext, GitContextConfig, GitRepo, GitRepoConfig


@pytest.fixture
def repo_config() -> GitRepoConfig:
    """Fixture for GitRepoConfig."""
    return GitRepoConfig(
        url="https://gitlab.example.com",
        group="mygroup",
        token=None,  # Updated to avoid SecretStr validation issue in test
        cache_dir=Path(tempfile.gettempdir()),
    )


@pytest.fixture
def git_repo(repo_config: GitRepoConfig) -> GitRepo:
    """Fixture for GitRepo."""
    repo = GitRepo(repo_config)
    # Mock executor to avoid threading issues in tests
    repo._executor = MagicMock()
    # Mock run_in_executor to execute immediately
    repo._executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    return repo


def test_git_repo_url_generation(git_repo: GitRepo) -> None:
    """Test standard repo URL generation."""
    url = git_repo._get_repo_url("arc123")
    assert url == "https://gitlab.example.com/mygroup/arc123.git"


def test_git_repo_context_config_generation(git_repo: GitRepo) -> None:
    """Test context config generation with cache dir."""
    config = git_repo._get_context_config("arc123")
    assert config.local_path is not None
    assert config.local_path == git_repo._config.cache_dir / "arc123"
    assert config.repo_url.get_secret_value() == "https://gitlab.example.com/mygroup/arc123.git"


def test_git_context_ensure_path(tmp_path: Path) -> None:
    """Test that GitContext creates local directories."""
    target_path = tmp_path / "deep" / "nested" / "repo"
    config = GitContextConfig(
        repo_url=SecretStr("https://example.com/repo.git"),
        branch="main",
        user_name=None,
        user_email=None,
        local_path=target_path,
    )

    context = GitContext(config)
    path = context._ensure_path()

    assert path == target_path
    assert path.parent.exists()
    # The actual leaf dir is created by git clone/init usually, but parent must exist


@patch("middleware.api.arc_store.git_repo.Repo")
def test_git_context_enter_clone(mock_repo: MagicMock, tmp_path: Path) -> None:
    """Test GitContext cloning behavior."""
    target_path = tmp_path / "repo"
    target_path.mkdir()

    config = GitContextConfig(
        repo_url=SecretStr("https://example.com/repo.git"),
        branch="main",
        user_name=None,
        user_email=None,
        local_path=target_path,
    )

    with GitContext(config) as ctx:
        assert ctx.path == str(target_path)
        # Verify clone called because .git doesn't exist
        mock_repo.clone_from.assert_called_once()

    # Verify close called
    mock_repo.clone_from.return_value.close.assert_called_once()


@patch("middleware.api.arc_store.git_repo.Repo")
def test_git_context_enter_existing(mock_repo: MagicMock, tmp_path: Path) -> None:
    """Test GitContext connecting to existing repo."""
    target_path = tmp_path / "repo"
    target_path.mkdir()
    (target_path / ".git").mkdir()

    config = GitContextConfig(
        repo_url=SecretStr("https://example.com/repo.git"),
        branch="main",
        user_name=None,
        user_email=None,
        local_path=target_path,
    )

    with GitContext(config) as ctx:
        # Verify NO clone called
        mock_repo.clone_from.assert_not_called()
        # Verify Repo(path) called
        mock_repo.assert_called()
        assert ctx.repo is not None


def test_default_cache_dir_validator() -> None:
    """Test Pydantic logic for default cache_dir."""
    # Strict mode test (should have been set by validator)
    config = GitRepoConfig(
        url="https://a",
        group="b",
        cache_dir=None,  # type: ignore[arg-type]
    )
    assert config.cache_dir is not None


@pytest.mark.asyncio
async def test_create_or_update(git_repo: GitRepo, tmp_path: Path) -> None:
    """Test _create_or_update logic."""
    arc = MagicMock()
    arc_id = "test_arc"

    # Mock loop and executor
    # Since we mocked repo._executor in fixture, we need to handle run_in_executor
    # But git_repo use `loop.run_in_executor`.
    # For asyncio tests, we can patch the loop or just rely on the actual loop running the synchronous lambda

    # Let's patch GitContext to avoid real git operations and file system
    with patch("middleware.api.arc_store.git_repo.GitContext") as mock_ctx:
        mock_ctx_instance = mock_ctx.return_value
        mock_ctx_instance.__enter__.return_value = mock_ctx_instance
        # Mock repo path
        fake_repo_path = tmp_path / "fake_repo"
        fake_repo_path.mkdir()
        # Create some junk to test cleanup
        (fake_repo_path / "junk.txt").write_text("junk")
        (fake_repo_path / ".git").mkdir()

        mock_ctx_instance.path = str(fake_repo_path)
        mock_ctx_instance.repo = MagicMock()

        # Run the method
        # Using real executor would spawn thread. Using sync lambda on mock executor:
        # loop.run_in_executor(None, fn) runs in default executor.
        # git_repo uses self._executor.

        # We need to ensure run_in_executor calls our function synchronously or awaits it.
        # Since we mocked self._executor in the fixture, but loop.run_in_executor implementation
        # calls executor.submit.

        # Actually, standard ThreadPoolExecutor logic works fine in tests usually,
        # but let's see.

        # For simplicity, we can let it run with the real thread pool (reverting the fixture mock?)
        # Or simpler: Patch run_in_executor to execute immediately.

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            # Make run_in_executor just call the function AND return a Future (or awaitable) because it is awaited
            # But wait, run_in_executor returns a Future. We await it.
            # If we make it call the function immediately, it returns the result of the function (None).
            # None is not awaitable.

            # We need to return a done future.

            # But the function needs to actually RUN.
            # So we can define a side_effect that runs the function and returns a done future.

            def run_and_return_future(
                _executor: object, func: Callable[..., Any], *args: object
            ) -> asyncio.Future[None]:
                # Run the function
                func(*args)
                # Return done future
                f: asyncio.Future[None] = asyncio.Future()
                f.set_result(None)
                return f

            mock_loop.run_in_executor.side_effect = run_and_return_future

            # Ensure path property mocks correctly
            type(mock_ctx_instance).path = PropertyMock(return_value=str(fake_repo_path))

            await git_repo._create_or_update(arc_id, arc)

            # Check cleanup
            assert not (fake_repo_path / "junk.txt").exists()
            assert (fake_repo_path / ".git").exists()

            # Check ARC write
            # pylint: disable=no-member
            arc.Write.assert_called_once_with(str(fake_repo_path))

            # Check commit/push
            mock_ctx_instance.commit_and_push.assert_called()


def test_get_arc_success(git_repo: GitRepo) -> None:
    """Test _get successfully loads ARC."""
    arc_id = "test_arc"

    with (
        patch("middleware.api.arc_store.git_repo.GitContext") as mock_ctx,
        patch("middleware.api.arc_store.git_repo.ARC") as mock_arc,
    ):
        mock_ctx_instance = mock_ctx.return_value
        mock_ctx_instance.__enter__.return_value = mock_ctx_instance
        mock_ctx_instance.path = "/tmp/fake/path"  # nosec B108
        mock_ctx_instance.repo = MagicMock()

        mock_arc.load.return_value = "MyARC"

        result = git_repo._get(arc_id)

        assert result == "MyARC"
        mock_arc.load.assert_called_once_with("/tmp/fake/path")  # nosec B108


def test_get_arc_repo_fail(git_repo: GitRepo) -> None:
    """Test _get handles repo init failure."""
    with patch("middleware.api.arc_store.git_repo.GitContext") as mock_ctx:  # , \
        #  patch("middleware.api.arc_store.git_repo.logger"):

        mock_ctx_instance = mock_ctx.return_value
        mock_ctx_instance.__enter__.return_value = mock_ctx_instance
        # Simulate failure to init repo
        mock_ctx_instance.repo = None

        result = git_repo._get("arc1")
        assert result is None


def test_get_arc_load_fail(git_repo: GitRepo) -> None:
    """Test _get handles ARC load failure."""
    with (
        patch("middleware.api.arc_store.git_repo.GitContext") as mock_ctx,
        patch("middleware.api.arc_store.git_repo.ARC") as mock_arc,
    ):
        mock_ctx_instance = mock_ctx.return_value
        mock_ctx_instance.__enter__.return_value = mock_ctx_instance
        mock_ctx_instance.repo = MagicMock()

        mock_arc.load.side_effect = Exception("Bad ARC")

        result = git_repo._get("arc1")
        assert result is None


def test_exists_true(git_repo: GitRepo) -> None:
    """Test _exists returns True."""
    with patch("git.cmd.Git") as mock_git:
        mock_git_instance = mock_git.return_value
        mock_git_instance.ls_remote.return_value = "hash ref"

        assert git_repo._exists("arc1") is True
        mock_git_instance.ls_remote.assert_called()


def test_exists_false(git_repo: GitRepo) -> None:
    """Test _exists returns False on error."""
    with patch("git.cmd.Git") as mock_git:
        mock_git_instance = mock_git.return_value
        mock_git_instance.ls_remote.side_effect = GitCommandError("ls-remote", "fail")

        assert git_repo._exists("arc1") is False


def test_delete(git_repo: GitRepo) -> None:
    """Test _delete just logs warning."""
    # Just ensure it doesn't raise
    git_repo._delete("arc1")
