"""Tests for dual-slot ArcStore resolution and config validation."""

import pytest
from pydantic import TypeAdapter, ValidationError

from middleware.api.arc_store.arc_store_config import ArcStoreBackendType, ArcStoreConfig, ConsolidatedStoreConfig
from middleware.api.arc_store.consolidated_git import ConsolidatedGitConfig
from middleware.api.arc_store.git_repo import GitRepoConfig
from middleware.api.arc_store.resolution import (
    has_consolidated_store,
    resolve_arc_store_backend,
    resolve_consolidated_store_settings,
)
from middleware.api.config import Config

_ARC_STORE_CONFIG: TypeAdapter[ArcStoreConfig] = TypeAdapter(ArcStoreConfig)


def _minimal_couchdb() -> dict[str, str]:
    return {"url": "http://localhost:5984", "db_name": "test"}


def _minimal_celery() -> dict[str, str]:
    return {"broker_url": "memory://"}


def _git_repo_arc_store() -> dict[str, object]:
    return {
        "git_repo": {"url": "https://gitlab.example/repo.git", "group": "fairagro"},
    }


def test_accept_git_repo_plus_optional_catalog() -> None:
    """Required arc_store plus optional consolidated_store validates."""
    config = Config.from_data({
        "couchdb": _minimal_couchdb(),
        "celery": _minimal_celery(),
        "arc_store": _git_repo_arc_store(),
        "consolidated_store": {
            "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
        },
    })
    backend_type, settings = resolve_arc_store_backend(config)
    assert backend_type == ArcStoreBackendType.GIT_REPO
    assert isinstance(settings, GitRepoConfig)
    assert has_consolidated_store(config)
    consol = resolve_consolidated_store_settings(config)
    assert isinstance(consol, ConsolidatedGitConfig)
    assert consol.repo_url == "file:///tmp/catalog.git"


def test_reject_consolidated_under_arc_store() -> None:
    """Catalog settings under arc_store are not permitted on the per-ARC slot."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Config.from_data({
            "couchdb": _minimal_couchdb(),
            "celery": _minimal_celery(),
            "arc_store": {
                "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
            },
        })


def test_reject_consolidated_alongside_git_repo_under_arc_store() -> None:
    """Catalog keys under arc_store are forbidden even when a per-ARC backend is set."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Config.from_data({
            "couchdb": _minimal_couchdb(),
            "celery": _minimal_celery(),
            "arc_store": {
                **_git_repo_arc_store(),
                "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
            },
        })


def test_obsolete_top_level_alone_fails_missing_arc_store() -> None:
    """Top-level store keys are not model fields; without arc_store validation fails."""
    with pytest.raises(ValidationError, match="arc_store"):
        Config.from_data({
            "couchdb": _minimal_couchdb(),
            "celery": _minimal_celery(),
            "git_repo": {"url": "https://gitlab.example/repo.git", "group": "fairagro"},
        })


def test_obsolete_top_level_ignored_when_arc_store_present() -> None:
    """Unknown top-level extras are ignored when required arc_store is valid."""
    config = Config.from_data({
        "couchdb": _minimal_couchdb(),
        "celery": _minimal_celery(),
        "arc_store": _git_repo_arc_store(),
        "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
    })
    assert config.consolidated_store is None
    assert not has_consolidated_store(config)


def test_arc_store_required() -> None:
    """Missing arc_store fails validation."""
    with pytest.raises(ValidationError):
        Config.from_data({
            "couchdb": _minimal_couchdb(),
            "celery": _minimal_celery(),
        })


def test_arc_store_config_requires_exactly_one_backend_key() -> None:
    """ArcStoreConfig rejects empty / dual / catalog-only nested keys."""
    with pytest.raises(ValidationError, match="exactly one"):
        _ARC_STORE_CONFIG.validate_python({})
    with pytest.raises(ValidationError, match="exactly one"):
        _ARC_STORE_CONFIG.validate_python({
            "git_repo": {"url": "https://gitlab.example/repo.git", "group": "fairagro"},
            "gitlab_api": {"url": "https://gitlab.example", "token": "x", "group": "g"},
        })
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _ARC_STORE_CONFIG.validate_python({
            "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
        })


def test_consolidated_store_shared_git_settings_merge() -> None:
    """consolidated_store.git supplies defaults; nested block overrides."""
    config = Config.from_data({
        "couchdb": _minimal_couchdb(),
        "celery": _minimal_celery(),
        "arc_store": _git_repo_arc_store(),
        "consolidated_store": {
            "git": {"branch": "develop", "user_name": "Shared Git"},
            "consolidated_git": {
                "repo_url": "file:///tmp/catalog.git",
                "branch": "main",
            },
        },
    })
    settings = resolve_consolidated_store_settings(config)
    assert isinstance(settings, ConsolidatedGitConfig)
    assert settings.branch == "main"
    assert settings.user_name == "Shared Git"


def test_consolidated_store_needs_no_type() -> None:
    """consolidated_store has no type field; slot name selects catalog."""
    assert "type" not in ConsolidatedStoreConfig.model_fields
    slot = ConsolidatedStoreConfig.model_validate({
        "consolidated_git": {"repo_url": "file:///tmp/catalog.git"},
    })
    assert slot.consolidated_git.repo_url == "file:///tmp/catalog.git"


def test_arc_store_shared_git_settings_merge() -> None:
    """arc_store.git supplies defaults; nested backend block overrides."""
    config = Config.from_data({
        "couchdb": _minimal_couchdb(),
        "celery": _minimal_celery(),
        "arc_store": {
            "git": {"branch": "develop", "user_name": "Shared Git"},
            "git_repo": {
                "url": "https://gitlab.example/repo.git",
                "group": "fairagro",
                "branch": "main",
            },
        },
    })
    _, settings = resolve_arc_store_backend(config)
    assert isinstance(settings, GitRepoConfig)
    assert settings.branch == "main"
    assert settings.user_name == "Shared Git"
