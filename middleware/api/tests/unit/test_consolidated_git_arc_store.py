"""Tests for ConsolidatedGitArcStore finalize and ephemeral clone behaviour."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git.exc import GitCommandError
from pydantic import SecretStr
from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.arc_store import ArcStoreError, ArcStoreTransientError
from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore, ConsolidatedGitConfig
from middleware.shared.config.logging import install_url_userinfo_redaction


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

    async def _iter_arcs(_rdi: str):
        yield ("arc-1", minimal_rocrate_dict("DS-1"))

    store.iter_arc_contents_by_rdi = MagicMock(side_effect=_iter_arcs)
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
        patch("middleware.api.arc_store.consolidated_git.store.tempfile.mkdtemp", return_value=str(work_dir)),
        patch("middleware.api.arc_store.consolidated_git.store.GitContext", return_value=ctx_instance),
        patch("middleware.api.arc_store.consolidated_git.store.shutil.rmtree") as mock_rmtree,
        patch("middleware.api.arc_store.consolidated_git.store.Path.exists", return_value=False),
        patch("middleware.api.arc_store.consolidated_git.store.Path.write_bytes"),
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
        stderr=(
            "! [rejected] main -> main (non-fast-forward)\n"
            "error: failed to push some refs to "
            "'https://oauth2:secret-token@gitlab.example.com/group/catalog.git'"
        ),
    )

    with (
        patch("middleware.api.arc_store.consolidated_git.store.tempfile.mkdtemp", return_value=str(work_dir)),
        patch("middleware.api.arc_store.consolidated_git.store.GitContext", return_value=ctx_instance),
        patch("middleware.api.arc_store.consolidated_git.store.shutil.rmtree"),
        patch("middleware.api.arc_store.consolidated_git.store.Path.exists", return_value=False),
        patch("middleware.api.arc_store.consolidated_git.store.Path.write_bytes"),
        pytest.raises(ArcStoreTransientError) as raised,
    ):
        store._publish_catalog_bytes("edal", b"[]\n")

    message = str(raised.value)
    assert "secret-token" not in message
    assert "https://***@gitlab.example.com/group/catalog.git" in message
    assert "non-fast-forward" in message


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
    doc_store.iter_arc_contents_by_rdi.assert_called_once_with("edal")
    mock_publish.assert_called_once()
    catalog_bytes = mock_publish.call_args[0][1]
    assert catalog_bytes.startswith(b"[")


@pytest.mark.asyncio
async def test_finalize_partial_push_skips_bad_arc_keeps_good(
    consolidated_config: ConsolidatedGitConfig,
) -> None:
    """Interim partial push: one bad ARC must not block publishing good Datasets."""
    doc_store = MagicMock()
    bad_arc = {
        "@context": "https://example.invalid/unknown-context",
        "@graph": [
            {"@id": "./", "@type": "Dataset", "identifier": "BAD", "name": "Broken context"},
        ],
    }

    async def _iter_arcs(_rdi: str):
        yield ("good-arc", minimal_rocrate_dict("DS-GOOD"))
        yield ("bad-arc", bad_arc)

    doc_store.iter_arc_contents_by_rdi = MagicMock(side_effect=_iter_arcs)
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)

    with patch.object(store, "_publish_catalog_bytes", return_value=True) as mock_publish:
        pushed = await store.finalize(rdi="edal")

    assert pushed is True
    catalog_bytes = mock_publish.call_args[0][1]
    assert b"DS-GOOD" in catalog_bytes
    assert b"Broken context" not in catalog_bytes


@pytest.mark.asyncio
async def test_finalize_all_arcs_fail_refuses_empty_wipe(
    consolidated_config: ConsolidatedGitConfig,
) -> None:
    """When every ARC fails, do not publish [] over an existing remote catalog."""
    doc_store = MagicMock()

    async def _iter_arcs(_rdi: str):
        yield ("bad-1", {"not": "an ro-crate"})
        yield ("bad-2", {"@graph": "nope"})

    doc_store.iter_arc_contents_by_rdi = MagicMock(side_effect=_iter_arcs)
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)

    with (
        patch.object(store, "_publish_catalog_bytes") as mock_publish,
        pytest.raises(ArcStoreError, match="refusing to publish an empty catalog"),
    ):
        await store.finalize(rdi="edal")

    mock_publish.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_empty_rdi_still_publishes_empty_catalog(
    consolidated_config: ConsolidatedGitConfig,
) -> None:
    """No CouchDB ARCs → empty catalog is allowed (legitimate empty RDI)."""
    doc_store = MagicMock()

    async def _iter_arcs(_rdi: str):
        return
        yield  # pragma: no cover — async generator with no items

    doc_store.iter_arc_contents_by_rdi = MagicMock(side_effect=_iter_arcs)
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)

    with patch.object(store, "_publish_catalog_bytes", return_value=True) as mock_publish:
        pushed = await store.finalize(rdi="edal")

    assert pushed is True
    assert mock_publish.call_args[0][1].strip() == b"[]"


@pytest.mark.asyncio
async def test_finalize_catalog_backend_flags(
    consolidated_config: ConsolidatedGitConfig,
    doc_store: MagicMock,
) -> None:
    """Consolidated backend flags per-ARC Git off and standalone upload off."""
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)
    assert store.publishes_per_arc_git is False
    assert store.supports_standalone_upload is False


def test_check_health_file_url_without_existing_path(tmp_path: Path) -> None:
    """file:// health is True even when the bare remote path does not exist yet."""
    missing = tmp_path / "nested" / "missing" / "catalog.git"
    config = ConsolidatedGitConfig(
        repo_url=f"file://{missing.resolve()}",
        cache_dir=tmp_path / "cache",
    )
    store = ConsolidatedGitArcStore(config, MagicMock())
    assert not missing.exists()
    assert not missing.parent.exists()
    assert store.check_health() is True


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

    with patch("middleware.api.arc_store.consolidated_git.store.git.cmd.Git", return_value=mock_git):
        assert store.check_health() is True

    mock_git.ls_remote.assert_called_once_with(
        "https://oauth2:secret-token@gitlab.example.com/group/catalog.git",
    )


def test_check_health_https_ls_remote_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Unreachable HTTPS catalog remotes report unhealthy without logging tokens."""
    config = ConsolidatedGitConfig(
        repo_url="https://gitlab.example.com/group/catalog.git",
        token=SecretStr("secret-token"),
        cache_dir=tmp_path / "cache",
    )
    store = ConsolidatedGitArcStore(config, MagicMock())
    mock_git = MagicMock()
    mock_git.ls_remote.side_effect = GitCommandError(
        "ls-remote",
        128,
        stderr="fatal: could not read from remote 'https://oauth2:secret-token@gitlab.example.com/group/catalog.git'",
    )

    install_url_userinfo_redaction()
    with (
        patch("middleware.api.arc_store.consolidated_git.store.git.cmd.Git", return_value=mock_git),
        caplog.at_level("WARNING"),
    ):
        assert store.check_health() is False

    assert "secret-token" not in caplog.text
    assert "https://***@gitlab.example.com/group/catalog.git" in caplog.text
