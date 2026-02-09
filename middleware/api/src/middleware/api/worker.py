"""Celery worker module for asynchronous ARC processing tasks.

This module provides:
- process_arc: Celery task for processing individual ARCs asynchronously
"""

import asyncio
import logging
from typing import Any

from middleware.api.celery_app import business_logic, celery_app

# Initialize logger
logger = logging.getLogger(__name__)


@celery_app.task(name="sync_arc_to_gitlab")
def sync_arc_to_gitlab(rdi: str, arc_data: dict[str, Any]) -> dict[str, Any]:
    """Sync ARC to GitLab asynchronously.

    This task is responsible for the slow GitLab synchronization phase.
    It is triggered by the API after the ARC has been successfully stored in CouchDB.

    Args:
        self: Celery task instance.
        rdi: Research Data Infrastructure identifier.
        arc_data: ARC data dictionary.

    Returns:
        Task result as dictionary.
    """
    if business_logic is None:
        logger.error("BusinessLogic not initialized")
        raise RuntimeError("BusinessLogic not initialized")

    logger.info("Starting GitLab sync task for RDI %s", rdi)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run_sync() -> None:
            async with business_logic:
                await business_logic.sync_to_gitlab(rdi, arc_data)

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
