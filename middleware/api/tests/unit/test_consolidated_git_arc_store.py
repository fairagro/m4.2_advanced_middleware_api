"""Tests for ConsolidatedGitArcStore finalize and ephemeral clone behaviour."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from git.exc import GitCommandError
from pydantic import SecretStr
from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.arc_store import ArcStoreError, ArcStoreTransientError
from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore
from middleware.api.arc_store.consolidated_git_config import ConsolidatedGitConfig


@pytest.fixture
def consolidated_config(tmp_path: Path) -> ConsolidatedGitConfig:
    """Consolidated Git config with isolated cache directory and file:// remote."""
    return ConsolidatedGitConfig(
        repo_url=f"file://{(tmp_path / 'catalog.git').resolve()}",
        cache_dir=tmp_path / "cache",
    )


@pytest.fixture
def doc_store() -> MagicMock:
    """Document store mock returning one ARC for finalize."""
    store = MagicMock()
    store.list_arc_contents_by_rdi = AsyncMock(
        return_value=[("arc-1", minimal_rocrate_dict("DS-1"))],
    )
    return store


def test_publish_catalog_bytes_removes_ephemeral_clone(
    consolidated_config: ConsolidatedGitConfig,
    tmp_path: Path,
) -> None:
    """``_publish_catalog_bytes`` always deletes its temp working directory."""
    store = ConsolidatedGitArcStore(consolidated_config, MagicMock())
    work_dir = tmp_path / "catalog_finalize_work"
    work_dir.mkdir()

    ctx_instance = MagicMock()
    ctx_instance.path = str(work_dir)
    ctx_instance.__enter__.return_value = ctx_instance

    with (
        patch("middleware.api.arc_store.consolidated_git.tempfile.mkdtemp", return_value=str(work_dir)),
        patch("middleware.api.arc_store.consolidated_git.GitContext", return_value=ctx_instance),
        patch("middleware.api.arc_store.consolidated_git.shutil.rmtree") as mock_rmtree,
        patch("middleware.api.arc_store.consolidated_git.Path.exists", return_value=False),
        patch("middleware.api.arc_store.consolidated_git.Path.write_bytes"),
    ):
        pushed = store._publish_catalog_bytes("edal", b"[]\n")

    assert pushed is True
    mock_rmtree.assert_called_once_with(work_dir, ignore_errors=True)


def test_publish_catalog_bytes_rejects_unsafe_rdi(consolidated_config: ConsolidatedGitConfig) -> None:
    """RDI must be a single safe filename segment (same charset as known_rdis)."""
    store = ConsolidatedGitArcStore(consolidated_config, MagicMock())
    with pytest.raises(ArcStoreError, match="Invalid RDI for catalog filename"):
        store._publish_catalog_bytes("../etc/passwd", b"[]\n")
    with pytest.raises(ArcStoreError, match="Invalid RDI for catalog filename"):
        store._publish_catalog_bytes("edal/nested", b"[]\n")
    with pytest.raises(ArcStoreError, match="Invalid RDI for catalog filename"):
        store._publish_catalog_bytes("", b"[]\n")


def test_publish_catalog_bytes_push_conflict_is_transient(
    consolidated_config: ConsolidatedGitConfig,
    tmp_path: Path,
) -> None:
    """Concurrent non-fast-forward push becomes ArcStoreTransientError for Celery retry."""
    store = ConsolidatedGitArcStore(consolidated_config, MagicMock())
    work_dir = tmp_path / "catalog_finalize_work"
    work_dir.mkdir()

    ctx_instance = MagicMock()
    ctx_instance.path = str(work_dir)
    ctx_instance.__enter__.return_value = ctx_instance
    ctx_instance.commit_and_push.side_effect = GitCommandError(
        "push",
        1,
        stderr="! [rejected] main -> main (non-fast-forward)\nerror: failed to push some refs",
    )

    with (
        patch("middleware.api.arc_store.consolidated_git.tempfile.mkdtemp", return_value=str(work_dir)),
        patch("middleware.api.arc_store.consolidated_git.GitContext", return_value=ctx_instance),
        patch("middleware.api.arc_store.consolidated_git.shutil.rmtree"),
        patch("middleware.api.arc_store.consolidated_git.Path.exists", return_value=False),
        patch("middleware.api.arc_store.consolidated_git.Path.write_bytes"),
        pytest.raises(ArcStoreTransientError),
    ):
        store._publish_catalog_bytes("edal", b"[]\n")


@pytest.mark.asyncio
async def test_finalize_loads_arcs_from_couchdb(
    consolidated_config: ConsolidatedGitConfig,
    doc_store: MagicMock,
) -> None:
    """Finalize rebuilds catalog bytes from CouchDB ARC bodies."""
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)

    with patch.object(store, "_publish_catalog_bytes", return_value=False) as mock_publish:
        pushed = await store.finalize(rdi="edal")

    assert pushed is False
    doc_store.list_arc_contents_by_rdi.assert_awaited_once_with("edal")
    mock_publish.assert_called_once()
    catalog_bytes = mock_publish.call_args[0][1]
    assert catalog_bytes.startswith(b"[")


@pytest.mark.asyncio
async def test_finalize_catalog_backend_flags(
    consolidated_config: ConsolidatedGitConfig,
    doc_store: MagicMock,
) -> None:
    """Consolidated backend flags per-ARC Git off and standalone upload off."""
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)
    assert store.publishes_per_arc_git is False
    assert store.supports_standalone_upload is False


def test_check_health_https_uses_ls_remote(tmp_path: Path) -> None:
    """HTTPS health checks probe the remote instead of only formatting the URL."""
    config = ConsolidatedGitConfig(
        repo_url="https://gitlab.example.com/group/catalog.git",
        token=SecretStr("secret-token"),
        cache_dir=tmp_path / "cache",
    )
    store = ConsolidatedGitArcStore(config, MagicMock())
    mock_git = MagicMock()
    mock_git.ls_remote.return_value = "deadbeef\trefs/heads/main\n"

    with patch("middleware.api.arc_store.consolidated_git.git.cmd.Git", return_value=mock_git):
        assert store.check_health() is True

    mock_git.ls_remote.assert_called_once_with(
        "https://oauth2:secret-token@gitlab.example.com/group/catalog.git",
    )


def test_check_health_https_ls_remote_failure(tmp_path: Path) -> None:
    """Unreachable HTTPS catalog remotes report unhealthy."""
    config = ConsolidatedGitConfig(
        repo_url="https://gitlab.example.com/group/catalog.git",
        cache_dir=tmp_path / "cache",
    )
    store = ConsolidatedGitArcStore(config, MagicMock())
    mock_git = MagicMock()
    mock_git.ls_remote.side_effect = GitCommandError("ls-remote", 128, stderr="fatal: could not read from remote")

    with patch("middleware.api.arc_store.consolidated_git.git.cmd.Git", return_value=mock_git):
        assert store.check_health() is False
