"""Resolve dual-slot ArcStore settings from ``arc_store`` / ``consolidated_store``."""

from __future__ import annotations

from typing import Protocol

from middleware.api.arc_store.arc_store_config import (
    ArcStoreBackendType,
    ArcStoreConfig,
    ConsolidatedStoreConfig,
)
from middleware.api.arc_store.consolidated_git import ConsolidatedGitConfig
from middleware.api.arc_store.git_cli_settings import merge_git_cli_settings
from middleware.api.arc_store.git_repo import GitRepoConfig
from middleware.api.arc_store.gitlab_api import GitlabApiConfig


class ArcStoreConfigSource(Protocol):
    """Minimal config surface for dual-slot ArcStore resolution."""

    arc_store: ArcStoreConfig
    consolidated_store: ConsolidatedStoreConfig | None


def validate_arc_store_config(config: ArcStoreConfigSource) -> None:
    """Ensure required ``arc_store`` resolves and optional consol. settings are valid."""
    resolve_arc_store_backend(config)
    resolve_consolidated_store_settings(config)


def resolve_arc_store_backend(
    config: ArcStoreConfigSource,
) -> tuple[ArcStoreBackendType, GitRepoConfig | GitlabApiConfig]:
    """Return per-ARC backend type and its settings model."""
    arc = config.arc_store
    if arc.git_repo is not None:
        return ArcStoreBackendType.GIT_REPO, merge_git_cli_settings(arc.git_repo, arc.git)
    if arc.gitlab_api is not None:
        return ArcStoreBackendType.GITLAB_API, arc.gitlab_api
    msg = "arc_store must set exactly one of 'git_repo' or 'gitlab_api'"
    raise ValueError(msg)


def resolve_consolidated_store_settings(config: ArcStoreConfigSource) -> ConsolidatedGitConfig | None:
    """Return merged consolidated catalog settings, or ``None`` when the slot is unset."""
    slot = config.consolidated_store
    if slot is None:
        return None
    return merge_git_cli_settings(slot.consolidated_git, slot.git)


def has_consolidated_store(config: ArcStoreConfigSource) -> bool:
    """Return whether the optional consolidated catalog slot is configured."""
    return resolve_consolidated_store_settings(config) is not None
