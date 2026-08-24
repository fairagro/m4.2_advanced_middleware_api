"""Factory for creating BusinessLogic instances."""

import logging
from typing import Literal

from ..arc_store.factory import create_arc_store
from ..document_store.couchdb import CouchDB
from .business_logic import BusinessLogic
from .config import BusinessLogicFactoryConfig
from .ports import BrokerHealthChecker, BusinessLogicPorts, TaskDispatcher

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
        doc_store = CouchDB(config.couchdb)
        store = create_arc_store(config, doc_store)

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
