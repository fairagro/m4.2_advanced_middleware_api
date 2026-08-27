"""Consolidated shared-repo catalog ArcStore backend."""

from middleware.api.arc_store.consolidated_git.config import ConsolidatedGitConfig
from middleware.api.arc_store.consolidated_git.store import ConsolidatedGitArcStore

__all__ = ["ConsolidatedGitArcStore", "ConsolidatedGitConfig"]
