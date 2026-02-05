"""Factory for creating BusinessLogic instances."""

import logging
from typing import Literal

from .arc_store import ArcStore
from .arc_store.git_repo import GitRepo
from .arc_store.gitlab_api import GitlabApi
from .business_logic import AsyncBusinessLogic, BusinessLogic, DirectBusinessLogic
from .config import Config
from .document_store.couchdb import CouchDB

logger = logging.getLogger(__name__)


class BusinessLogicFactory:
    """Factory to assemble BusinessLogic instances."""

    @staticmethod
    def create(config: Config, mode: Literal["dispatcher", "processor"]) -> BusinessLogic:
        """Create a BusinessLogic instance provided a config and mode.

        Args:
            config: Middleware API configuration.
            mode: 'dispatcher' for API (async task submission) or 'processor' for Worker
                  (direct processing with Stores).

        Returns:
            BusinessLogic: Initialized logic implementation.
        """
        if mode == "dispatcher":
            # For Dispatcher, we need the task sender.
            from .worker import process_arc  # pylint: disable=import-outside-toplevel

            # The 'delay' attribute of the task acts as the sender
            return AsyncBusinessLogic(task_sender=process_arc)

        elif mode == "processor":
            # Initialize Stores
            store: ArcStore
            if config.gitlab_api:
                store = GitlabApi(config.gitlab_api)
            elif config.git_repo:
                store = GitRepo(config.git_repo)
            else:
                raise ValueError("Invalid ArcStore configuration")

            # Initialize Document Store
            # Note: CouchDB document store connects lazily or explicitly.
            # DirectBusinessLogic does not call connect() automatically unless we add it to lifecycle.
            # However, previous Architecture assumed lifecycle management in Api.
            # Here, we create it. The consumer (e.g. Worker) should handle connect/close
            # OR we handle it within BusinessLogic.
            # Given that DirectBusinessLogic is now the 'Core', the DocumentStore dependency
            # is passed in.

            doc_store = CouchDB(config.couchdb)

            # We don't connect here, because connect is async and create is sync.
            # The worker/app utilizing this instance must ensure connections are open.

            return DirectBusinessLogic(store=store, doc_store=doc_store)

        else:
            raise ValueError(f"Unknown mode: {mode}")
