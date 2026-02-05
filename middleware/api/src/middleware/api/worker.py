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
            # Initialize CouchDB context for this task
            import os
            from middleware.api.couchdb_client import CouchDBClient
            from middleware.api.document_store.couchdb import CouchDB
            
            couchdb_url = os.environ.get("COUCHDB_URL", "http://localhost:5984")
            couchdb_user = os.environ.get("COUCHDB_USER")
            couchdb_password = os.environ.get("COUCHDB_PASSWORD")
            
            client = CouchDBClient(couchdb_url, couchdb_user, couchdb_password)
            try:
                # We attempt to connect, but if it fails we might log and proceed without CouchDB
                # (similar to fallback logic in business_logic, but here we can check connection)
                await client.connect()
                doc_store = CouchDB(client)
            except Exception as e:
                logger.warning("Failed to initialize CouchDB for worker task: %s", e)
                # Fallback to None (Git-only)
                doc_store = None
            
            try:
                return await business_logic.create_or_update_arc(rdi, arc_data, client_id, doc_store=doc_store)
            finally:
                if client:
                    await client.close()

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
