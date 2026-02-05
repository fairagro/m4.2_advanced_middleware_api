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


@celery_app.task(name="process_arc")
def process_arc(rdi: str, arc_data: dict[str, Any], client_id: str | None) -> dict[str, Any]:
    """Process a single ARC asynchronously.

    Args:
        rdi: Research Data Infrastructure identifier
        arc_data: ARC data dictionary
        client_id: Optional client identifier

    Returns:
        Task result as dictionary

    Raises:
        RuntimeError: If business logic is not initialized
    """
    if business_logic is None:
        logger.error("BusinessLogic not initialized")
        raise RuntimeError("BusinessLogic not initialized")

    logger.info("Starting processing task for RDI %s", rdi)

    # Run the async business logic in a sync wrapper
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def _run_logic():
            try:
                await business_logic.connect()
                return await business_logic.create_or_update_arc(rdi, arc_data, client_id or "unknown")
            finally:
                await business_logic.close()

        # Process a single ARC
        result = loop.run_until_complete(_run_logic())
        loop.close()

        # The result is an ArcOperationResult object (Pydantic model)
        # We return the dict representation
        return result.model_dump()

    except Exception as e:
        logger.error("Task failed: %s", e, exc_info=True)
        # Re-raise to mark task as failed in Celery
        raise e
