"""Resolve effective ArcStore backend from ``arc_store`` or legacy top-level keys."""

from __future__ import annotations

import warnings
from typing import Protocol

from pydantic import BaseModel

from .arc_store_config import (
    ArcStoreBackendType,
    ArcStoreConfig,
    ConsolidatedGitArcStoreConfig,
    GitlabApiArcStoreConfig,
    GitRepoArcStoreConfig,
)
from .config import GitRepoConfig
from .consolidated_git_config import ConsolidatedGitConfig
from .git_cli_settings import GitCliSettings, merge_git_cli_settings
from .gitlab_api import GitlabApiConfig
from .legacy_config import (
    OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT,
    OBSOLETE_TOP_LEVEL_GIT_REPO,
    OBSOLETE_TOP_LEVEL_GITLAB_API,
    count_obsolete_top_level_arc_store_fields,
)


class ArcStoreConfigSource(Protocol):
    """Minimal config surface for ArcStore backend resolution."""

    arc_store: ArcStoreConfig | None
    git_repo: GitRepoConfig | None
    gitlab_api: GitlabApiConfig | None
    consolidated_git: ConsolidatedGitConfig | None


def validate_arc_store_config(config: ArcStoreConfigSource) -> None:
    """Ensure exactly one effective ArcStore backend is configured."""
    resolve_arc_store_backend(config)


def _apply_shared_git_settings(
    backend: GitRepoConfig | ConsolidatedGitConfig,
    shared: GitCliSettings | None,
) -> GitRepoConfig | ConsolidatedGitConfig:
    return merge_git_cli_settings(backend, shared)


def _resolve_from_arc_store(
    arc: ArcStoreConfig,
) -> tuple[ArcStoreBackendType, GitRepoConfig | GitlabApiConfig | ConsolidatedGitConfig]:
    if isinstance(arc, GitRepoArcStoreConfig):
        return arc.type, _apply_shared_git_settings(arc.git_repo, arc.git)
    if isinstance(arc, GitlabApiArcStoreConfig):
        return arc.type, arc.gitlab_api
    if isinstance(arc, ConsolidatedGitArcStoreConfig):
        return arc.type, _apply_shared_git_settings(arc.consolidated_git, arc.git)
    msg = f"Unsupported arc_store config type: {type(arc).__name__}"
    raise TypeError(msg)


def resolve_arc_store_backend(
    config: ArcStoreConfigSource,
) -> tuple[ArcStoreBackendType, GitRepoConfig | GitlabApiConfig | ConsolidatedGitConfig]:
    """Return backend type and its settings model."""
    if not isinstance(config, BaseModel):
        msg = f"ArcStore config source must be a Pydantic model, got {type(config).__name__}"
        raise TypeError(msg)
    legacy_count = count_obsolete_top_level_arc_store_fields(config)

    if config.arc_store is not None:
        if legacy_count > 0:
            msg = "Configure either arc_store or legacy top-level store keys, not both"
            raise ValueError(msg)
        return _resolve_from_arc_store(config.arc_store)

    if legacy_count == 0:
        raise ValueError("One of arc_store or git_repo, gitlab_api, consolidated_git must be configured")
    if legacy_count > 1:
        raise ValueError("Only one ArcStore backend can be configured")

    # Read via ``__dict__`` so unset deprecated fields do not emit access warnings.
    # Emit exactly one explicit warning for the configured obsolete key.
    git_repo = config.__dict__.get("git_repo")
    if git_repo is not None:
        warnings.warn(OBSOLETE_TOP_LEVEL_GIT_REPO, DeprecationWarning, stacklevel=2)
        return ArcStoreBackendType.GIT_REPO, git_repo
    gitlab_api = config.__dict__.get("gitlab_api")
    if gitlab_api is not None:
        warnings.warn(OBSOLETE_TOP_LEVEL_GITLAB_API, DeprecationWarning, stacklevel=2)
        return ArcStoreBackendType.GITLAB_API, gitlab_api
    consolidated_git = config.__dict__.get("consolidated_git")
    if consolidated_git is not None:
        warnings.warn(OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT, DeprecationWarning, stacklevel=2)
        return ArcStoreBackendType.CONSOLIDATED_GIT, consolidated_git
    raise ValueError("One of arc_store or git_repo, gitlab_api, consolidated_git must be configured")


def is_consolidated_backend(config: ArcStoreConfigSource) -> bool:
    """Return whether the effective backend is consolidated Git catalog."""
    backend_type, _ = resolve_arc_store_backend(config)
    return backend_type == ArcStoreBackendType.CONSOLIDATED_GIT
