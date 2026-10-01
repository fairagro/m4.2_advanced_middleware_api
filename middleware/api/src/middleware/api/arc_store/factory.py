"""Construct ArcStore implementations from API/worker configuration."""

from __future__ import annotations

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore
from middleware.api.arc_store.git_repo import GitRepo
from middleware.api.arc_store.resolution import (
    ArcStoreConfigSource,
    resolve_arc_store_backend,
    resolve_consolidated_store_settings,
)
from middleware.api.document_store import DocumentStore


def create_arc_stores(config: ArcStoreConfigSource, doc_store: DocumentStore) -> tuple[ArcStore, ArcStore | None]:
    """Build the required per-ARC store and optional consolidated catalog store."""
    arc_store: ArcStore = GitRepo(resolve_arc_store_backend(config))

    consol_settings = resolve_consolidated_store_settings(config)
    if consol_settings is None:
        return arc_store, None
    return arc_store, ConsolidatedGitArcStore(consol_settings, doc_store)
