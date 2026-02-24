"""Factory for creating BusinessLogic instances."""

import logging
from typing import Literal

from .arc_store import ArcStore
from .arc_store.git_repo import GitRepo
from .arc_store.gitlab_api import GitlabApi
from .business_logic import BusinessLogic, TaskDispatcher, ArcSyncTask
from .config import Config
from .document_store.couchdb import CouchDB

from typing import Any, Literal

logger = logging.getLogger(__name__)


class CeleryTaskDispatcher:
    """Dispatcher that uses Celery to send tasks by name."""

    def __init__(self, celery_app):
        self._celery_app = celery_app

    def dispatch_sync_arc(self, task: ArcSyncTask) -> None:
        """Dispatch sync_arc_to_gitlab task to Celery."""
        self._celery_app.send_task("sync_arc_to_gitlab", args=(task.model_dump(),))


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

        # For API mode, provide task dispatcher
        task_dispatcher = None
        if mode == "api":
            from .celery_app import celery_app
            task_dispatcher = CeleryTaskDispatcher(celery_app)

        return BusinessLogic(config=config, store=store, doc_store=doc_store, task_dispatcher=task_dispatcher)
