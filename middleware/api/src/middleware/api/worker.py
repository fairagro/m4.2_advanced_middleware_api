"""Celery worker module for asynchronous ARC processing tasks.

This module provides:
- MiddlewareTask: Base task class with BusinessLogic initialization
- process_arc: Celery task for processing individual ARCs asynchronously
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from celery import Task

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.git_repo import GitRepo
from middleware.api.arc_store.gitlab_api import GitlabApi
from middleware.api.business_logic import BusinessLogic
from middleware.api.celery_app import celery_app
from middleware.api.config import Config

# Initialize logger
logger = logging.getLogger(__name__)


class MiddlewareTask(Task):
    """Base task class that ensures BusinessLogic is initialized."""

    # Class attribute to store the BusinessLogic instance (shared across all task instances)
    _business_logic: BusinessLogic | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Initialize resources before task execution."""
        if MiddlewareTask._business_logic is None:
            config_file = Path(os.environ.get("MIDDLEWARE_API_CONFIG", "/run/secrets/middleware-api-config"))
            if config_file.is_file():
                config = Config.from_yaml_file(config_file)
            else:
                # Fallback or error if config is missing
                logger.error("Config file not found: %s", config_file)
                raise RuntimeError("Config file not found")

            # Initialize ArcStore based on config
            store: ArcStore | None = None
            if config.gitlab_api:
                store = GitlabApi(config.gitlab_api)
            elif config.git_repo:
                store = GitRepo(config.git_repo)
            else:
                raise ValueError("Invalid ArcStore configuration")

            MiddlewareTask._business_logic = BusinessLogic(store)

        return self.run(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the task. Must be implemented by Celery task functions."""
        raise NotImplementedError("Subclasses or task functions must implement run()")

    @classmethod
    def get_business_logic(cls) -> BusinessLogic:
        """Get the initialized BusinessLogic instance.

        Returns:
            BusinessLogic: The initialized business logic instance.

        Raises:
            RuntimeError: If business logic has not been initialized.
        """
        if cls._business_logic is None:
            raise RuntimeError("Business logic not initialized")
        return cls._business_logic


@celery_app.task(bind=True, base=MiddlewareTask, name="process_arc")
def process_arc(self: MiddlewareTask, rdi: str, arc_data: dict[str, Any], client_id: str | None) -> dict[str, Any]:
    """Process a single ARC asynchronously."""
    # Get the business logic instance using the public method
    business_logic = MiddlewareTask.get_business_logic()

    logger.info("Starting processing task %s for RDI %s", self.request.id, rdi)

    # Run the async business logic in a sync wrapper

    try:
        # We process a list of 1 ARC to reuse the existing batch processing logic
        # wrapping it in a coroutine call
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # We need to construct a list of one ARC
        result = loop.run_until_complete(business_logic.create_or_update_arcs(rdi, [arc_data], client_id))
        loop.close()

        # The result is a CreateOrUpdateArcsResponse object (Pydantic model)
        # We return the dict representation
        return result.model_dump()

    except Exception as e:
        logger.error("Task failed: %s", e, exc_info=True)
        # Re-raise to mark task as failed in Celery
        raise e
