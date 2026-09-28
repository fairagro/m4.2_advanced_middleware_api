"""Construct ArcStore implementations from API/worker configuration."""

from __future__ import annotations

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.arc_store_config import ArcStoreBackendType
from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore, ConsolidatedGitConfig
from middleware.api.arc_store.git_repo import GitRepo, GitRepoConfig
from middleware.api.arc_store.gitlab_api import GitlabApi, GitlabApiConfig
from middleware.api.arc_store.resolution import (
    ArcStoreConfigSource,
    resolve_arc_store_backend,
    resolve_consolidated_store_settings,
)
from middleware.api.document_store import DocumentStore


def _build_per_arc_store(backend_type: ArcStoreBackendType, settings: GitRepoConfig | GitlabApiConfig) -> ArcStore:
    if backend_type == ArcStoreBackendType.GIT_REPO:
        if not isinstance(settings, GitRepoConfig):
            msg = f"Expected GitRepoConfig for git_repo backend, got {settings.__class__.__name__}"
            raise TypeError(msg)
        return GitRepo(settings)
    if backend_type == ArcStoreBackendType.GITLAB_API:
        if not isinstance(settings, GitlabApiConfig):
            msg = f"Expected GitlabApiConfig for gitlab_api backend, got {settings.__class__.__name__}"
            raise TypeError(msg)
        return GitlabApi(settings)
    msg = f"Unsupported per-ARC ArcStore backend: {backend_type}"
    raise TypeError(msg)


def create_arc_stores(config: ArcStoreConfigSource, doc_store: DocumentStore) -> tuple[ArcStore, ArcStore | None]:
    """Build the required per-ARC store and optional consolidated catalog store."""
    backend_type, settings = resolve_arc_store_backend(config)
    arc_store = _build_per_arc_store(backend_type, settings)

    consol_settings = resolve_consolidated_store_settings(config)
    if consol_settings is None:
        return arc_store, None
    if not isinstance(consol_settings, ConsolidatedGitConfig):
        msg = f"Expected ConsolidatedGitConfig for consolidated_store, got {consol_settings.__class__.__name__}"
        raise TypeError(msg)
    return arc_store, ConsolidatedGitArcStore(consol_settings, doc_store)
