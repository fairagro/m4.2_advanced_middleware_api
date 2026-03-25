"""Factory for creating BusinessLogic instances."""

import logging
from typing import Literal

from ..arc_store import ArcStore
from ..arc_store.git_repo import GitRepo
from ..arc_store.gitlab_api import GitlabApi
from ..document_store.couchdb import CouchDB
from .business_logic import BusinessLogic
from .config import BusinessLogicFactoryConfig
from .exceptions import TaskDispatcher
from .ports import BrokerHealthChecker, BusinessLogicPorts

logger = logging.getLogger(__name__)


class BusinessLogicFactory:
    """Factory to assemble BusinessLogic instances."""

    @staticmethod
    def create(
        config: BusinessLogicFactoryConfig,
        mode: Literal["api", "worker"],
        task_dispatcher: TaskDispatcher | None = None,
        broker_health_checker: BrokerHealthChecker | None = None,
    ) -> BusinessLogic:
        """Create a BusinessLogic instance provided a config and mode.

        Args:
            config: Middleware API configuration.
            mode: 'api' for API server (with GitLab sync task sender) or 'worker' for
                  background worker (without task sender).
            task_dispatcher: Task dispatcher implementation for API mode.
            broker_health_checker: Broker health checker implementation for API mode.

        Returns:
            BusinessLogic: Initialized logic implementation.
        """
        # Initialize Stores (both API and Worker need these)
        store: ArcStore
        if config.git_repo:
            store = GitRepo(config.git_repo)
        elif config.gitlab_api:
            # GitlabApi is deprecated, but we keep it for backward compatibility
            # until removed from Config.
            store = GitlabApi(config.gitlab_api)
        else:
            raise ValueError("Invalid ArcStore configuration")

        # Initialize Document Store
        doc_store = CouchDB(config.couchdb)

        if mode == "api" and task_dispatcher is None:
            raise ValueError("API mode requires a configured task_dispatcher")

        return BusinessLogic(
            config=config,
            store=store,
            doc_store=doc_store,
            ports=BusinessLogicPorts(
                task_dispatcher=task_dispatcher,
                broker_health_checker=broker_health_checker,
            ),
        )
