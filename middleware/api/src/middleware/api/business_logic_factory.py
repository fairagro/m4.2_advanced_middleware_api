"""Factory for creating BusinessLogic instances."""

import logging
from typing import Literal

from .arc_store import ArcStore
from .arc_store.git_repo import GitRepo
from .arc_store.gitlab_api import GitlabApi
from .business_logic import BusinessLogic
from .config import Config
from .document_store.couchdb import CouchDB
from .worker import sync_arc_to_gitlab

logger = logging.getLogger(__name__)


class BusinessLogicFactory:
    """Factory to assemble BusinessLogic instances."""

    @staticmethod
    def create(config: Config, mode: Literal["api", "worker"]) -> BusinessLogic:
        """Create a BusinessLogic instance provided a config and mode.

        Args:
            config: Middleware API configuration.
            mode: 'api' for API server (with GitLab sync task sender) or 'worker' for
                  background worker (without task sender).

        Returns:
            BusinessLogic: Initialized logic implementation.
        """
        # Initialize Stores (both API and Worker need these)
        store: ArcStore
        if config.gitlab_api:
            store = GitlabApi(config.gitlab_api)
        elif config.git_repo:
            store = GitRepo(config.git_repo)
        else:
            raise ValueError("Invalid ArcStore configuration")

        # Initialize Document Store
        doc_store = CouchDB(config.couchdb)

        # For API mode, provide GitLab sync task sender
        git_sync_task = None
        if mode == "api":
            git_sync_task = sync_arc_to_gitlab

        return BusinessLogic(config=config, store=store, doc_store=doc_store, git_sync_task=git_sync_task)
