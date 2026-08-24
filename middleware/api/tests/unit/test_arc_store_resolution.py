"""Tests for ArcStore backend resolution and config validation."""

import pytest
from pydantic import TypeAdapter, ValidationError

from middleware.api.arc_store.arc_store_config import ArcStoreBackendType, ArcStoreConfig
from middleware.api.arc_store.consolidated_git_config import ConsolidatedGitConfig
from middleware.api.arc_store.resolution import is_consolidated_backend, resolve_arc_store_backend
from middleware.api.config import Config

_ARC_STORE_CONFIG: TypeAdapter[ArcStoreConfig] = TypeAdapter(ArcStoreConfig)


def _minimal_couchdb() -> dict[str, str]:
    return {"url": "http://localhost:5984", "db_name": "test"}


def _minimal_celery() -> dict[str, str]:
    return {"broker_url": "memory://"}


def test_arc_store_type_consolidated_git() -> None:
    """Preferred arc_store.type selects consolidated backend."""
    config = Config.from_data({
        "couchdb": _minimal_couchdb(),
        "celery": _minimal_celery(),
        "arc_store": {
            "type": "consolidated_git",
            "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
        },
    })
    backend_type, settings = resolve_arc_store_backend(config)
    assert backend_type == ArcStoreBackendType.CONSOLIDATED_GIT
    assert isinstance(settings, ConsolidatedGitConfig)
    assert is_consolidated_backend(config)


def test_legacy_git_repo_still_works() -> None:
    """Obsolete top-level git_repo remains accepted."""
    with pytest.warns(DeprecationWarning, match="Top-level git_repo is obsolete"):
        config = Config.from_data({
            "couchdb": _minimal_couchdb(),
            "celery": _minimal_celery(),
            "git_repo": {"url": "https://gitlab.example/repo.git", "group": "fairagro"},
        })
    backend_type, _ = resolve_arc_store_backend(config)
    assert backend_type == ArcStoreBackendType.GIT_REPO


def test_reject_dual_arc_store_and_legacy() -> None:
    """arc_store plus legacy top-level key is invalid."""
    with pytest.raises(ValueError, match="not both"):
        Config.from_data({
            "couchdb": _minimal_couchdb(),
            "celery": _minimal_celery(),
            "git_repo": {"url": "https://gitlab.example/repo.git", "group": "fairagro"},
            "arc_store": {
                "type": "consolidated_git",
                "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
            },
        })


def test_arc_store_config_requires_nested_block() -> None:
    """arc_store.type must include matching nested settings."""
    with pytest.raises(ValidationError, match="consolidated_git"):
        _ARC_STORE_CONFIG.validate_python({"type": "consolidated_git"})


def test_arc_store_shared_git_settings_merge() -> None:
    """arc_store.git supplies defaults; nested backend block overrides."""
    config = Config.from_data({
        "couchdb": _minimal_couchdb(),
        "celery": _minimal_celery(),
        "arc_store": {
            "type": "consolidated_git",
            "git": {"branch": "develop", "user_name": "Shared Git"},
            "consolidated_git": {
                "repo_url": "file:///tmp/catalog.git",
                "branch": "main",
            },
        },
    })
    _, settings = resolve_arc_store_backend(config)
    assert isinstance(settings, ConsolidatedGitConfig)
    assert settings.branch == "main"
    assert settings.user_name == "Shared Git"
