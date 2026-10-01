"""Resolve dual-slot ArcStore settings from ``arc_store`` / ``consolidated_store``."""

from __future__ import annotations

from typing import Protocol

from middleware.api.arc_store.arc_store_config import (
    ArcStoreConfig,
    ConsolidatedStoreConfig,
)
from middleware.api.arc_store.consolidated_git import ConsolidatedGitConfig
from middleware.api.arc_store.git_cli_settings import merge_git_cli_settings
from middleware.api.arc_store.git_repo import GitRepoConfig


class ArcStoreConfigSource(Protocol):
    """Minimal config surface for dual-slot ArcStore resolution."""

    arc_store: ArcStoreConfig
    consolidated_store: ConsolidatedStoreConfig | None


def normalize_git_repo_rdi_gitlab_topics(arc_store: ArcStoreConfig, known_rdis: list[str]) -> ArcStoreConfig:
    """Return ``arc_store`` with ``rdi_gitlab_topics`` validated for ``known_rdis`` when applicable."""
    if not known_rdis:
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


def resolve_arc_store_backend(config: ArcStoreConfigSource) -> GitRepoConfig:
    """Return per-ARC GitRepo settings (merged with optional shared ``git``)."""
    arc = config.arc_store
    return merge_git_cli_settings(arc.git_repo, arc.git)


def resolve_consolidated_store_settings(config: ArcStoreConfigSource) -> ConsolidatedGitConfig | None:
    """Return merged consolidated catalog settings, or ``None`` when the slot is unset."""
    slot = config.consolidated_store
    if slot is None:
        return None
    return merge_git_cli_settings(slot.consolidated_git, slot.git)


def has_consolidated_store(config: ArcStoreConfigSource) -> bool:
    """Return whether the optional consolidated catalog slot is configured."""
    return resolve_consolidated_store_settings(config) is not None
