"""Celery worker module for asynchronous ARC processing tasks.

This module provides:
- process_arc: Celery task for processing individual ARCs asynchronously
"""

import asyncio
import logging
from typing import Any

from middleware.api.business_logic import BusinessLogic

from .business_logic_factory import BusinessLogicFactory
from .celery_app import celery_app, loaded_config

# Initialize logger
logger = logging.getLogger(__name__)


# Lazy initialization of BusinessLogic
class BusinessLogicManager:
    """Manages the lazy initialization and retrieval of the BusinessLogic instance for the worker."""

    _business_logic: BusinessLogic | None = None

    @classmethod
    def get_business_logic(cls) -> BusinessLogic:
        """Get or initialize the BusinessLogic instance for the worker."""
        if cls._business_logic is None:
            cls._business_logic = BusinessLogicFactory.create(loaded_config, mode="worker")
            logger.info("BusinessLogic initialized for worker")

        return cls._business_logic


@celery_app.task(name="sync_arc_to_gitlab")
def sync_arc_to_gitlab(rdi: str, arc_data: dict[str, Any]) -> dict[str, Any]:
    """Sync ARC to GitLab asynchronously.

    This task is responsible for the slow GitLab synchronization phase.
    It is triggered by the API after the ARC has been successfully stored in CouchDB.

    Args:
        rdi: Research Data Infrastructure identifier.
        arc_data: ARC data dictionary.

    Returns:
        Task result as dictionary.
    """
    logger.info("Starting GitLab sync task for RDI %s", rdi)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run_sync() -> None:
            logic: BusinessLogic = BusinessLogicManager.get_business_logic()
            # pylint: disable=not-async-context-manager
            async with logic:
                await logic.sync_to_gitlab(rdi, arc_data)

        loop.run_until_complete(_run_sync())
        loop.close()

        return {
            "status": "synced",
            "message": "Successfully synced to GitLab",
            "rdi": rdi,
        }

    except Exception as e:
        logger.error("GitLab sync task failed: %s", e, exc_info=True)
        # Re-raise to mark task as failed in Celery
        raise e
