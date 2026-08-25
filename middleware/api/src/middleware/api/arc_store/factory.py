"""Construct ArcStore implementations from API/worker configuration."""

from __future__ import annotations

from middleware.api.document_store import DocumentStore

from . import ArcStore
from .arc_store_config import ArcStoreBackendType
from .config import GitRepoConfig
from .consolidated_git import ConsolidatedGitArcStore
from .consolidated_git_config import ConsolidatedGitConfig
from .git_repo import GitRepo
from .gitlab_api import GitlabApi, GitlabApiConfig
from .resolution import ArcStoreConfigSource, resolve_arc_store_backend


def create_arc_store(config: ArcStoreConfigSource, doc_store: DocumentStore) -> ArcStore:
    """Build the configured ArcStore backend."""
    backend_type, settings = resolve_arc_store_backend(config)

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
    if not isinstance(settings, ConsolidatedGitConfig):
        msg = f"Expected ConsolidatedGitConfig for consolidated_git backend, got {settings.__class__.__name__}"
        raise TypeError(msg)
    return ConsolidatedGitArcStore(settings, doc_store)
