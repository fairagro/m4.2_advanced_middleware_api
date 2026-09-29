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


def normalize_git_repo_rdi_gitlab_topics(arc_store: ArcStoreConfig, known_rdis: list[str]) -> ArcStoreConfig:
    """Return ``arc_store`` with ``rdi_gitlab_topics`` validated for ``known_rdis`` when applicable."""
    if arc_store.git_repo is None or not known_rdis:
        return arc_store
    git_repo = arc_store.git_repo
    validated_topics = GitRepoConfig.validate_rdi_gitlab_topics_for_known_rdis(
        known_rdis,
        git_repo.rdi_gitlab_topics,
    )
    return arc_store.model_copy(
        update={"git_repo": git_repo.model_copy(update={"rdi_gitlab_topics": validated_topics})}
    )


def validate_arc_store_config(config: ArcStoreConfigSource, *, known_rdis: list[str]) -> ArcStoreConfig:
    """Validate dual-slot ArcStore config and normalize GitLab topic mapping.

    Returns:
        The (possibly updated) ``arc_store`` with validated ``rdi_gitlab_topics``.
    """
    resolve_arc_store_backend(config)
    resolve_consolidated_store_settings(config)
    return normalize_git_repo_rdi_gitlab_topics(config.arc_store, known_rdis)


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
