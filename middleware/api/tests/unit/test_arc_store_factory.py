"""Unit tests for dual-slot ``create_arc_stores`` port typing."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from middleware.api.arc_store import ArcStore, ConsolidatedArcStore
from middleware.api.arc_store.arc_store_config import ArcStoreConfig, ConsolidatedStoreConfig
from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore, ConsolidatedGitConfig
from middleware.api.arc_store.factory import create_arc_stores
from middleware.api.arc_store.git_repo import GitRepo, GitRepoConfig


def test_create_arc_stores_types_per_arc_only(tmp_path: Path) -> None:
    """Without consolidated_store, factory returns ArcStore / GitRepo and None."""
    config = SimpleNamespace(
        arc_store=ArcStoreConfig(
            git_repo=GitRepoConfig(
                url="https://gitlab.example.com",
                group="g",
                cache_dir=tmp_path / "arc-cache",
            )
        ),
        consolidated_store=None,
    )
    store, consolidated = create_arc_stores(config, MagicMock())
    assert isinstance(store, ArcStore)
    assert isinstance(store, GitRepo)
    assert consolidated is None
    assert not hasattr(store, "finalize")


def test_create_arc_stores_types_both_ports(tmp_path: Path) -> None:
    """With consolidated_store, slots are ArcStore vs ConsolidatedArcStore implementations."""
    config = SimpleNamespace(
        arc_store=ArcStoreConfig(
            git_repo=GitRepoConfig(
                url="https://gitlab.example.com",
                group="g",
                cache_dir=tmp_path / "arc-cache",
            )
        ),
        consolidated_store=ConsolidatedStoreConfig(
            consolidated_git=ConsolidatedGitConfig(
                repo_url=f"file://{(tmp_path / 'catalog.git').resolve()}",
                cache_dir=tmp_path / "catalog-cache",
            )
        ),
    )
    store, consolidated = create_arc_stores(config, MagicMock())
    assert isinstance(store, ArcStore)
    assert isinstance(store, GitRepo)
    assert isinstance(consolidated, ConsolidatedArcStore)
    assert isinstance(consolidated, ConsolidatedGitArcStore)
    assert not hasattr(store, "finalize")
    assert hasattr(consolidated, "finalize")
    assert not hasattr(consolidated, "create_or_update")
