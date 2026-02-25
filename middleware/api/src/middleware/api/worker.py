"""Celery worker module for asynchronous ARC processing tasks.

This module provides:
- sync_arc_to_gitlab: Celery task for synchronizing individual ARCs to GitLab asynchronously
"""

import asyncio
import logging
import threading

from middleware.api.business_logic import BusinessLogic, BusinessLogicFactory, TransientError

from .celery_app import celery_app, loaded_config
from .schemas.celery_tasks import ArcSyncTask

# Initialize logger
logger = logging.getLogger(__name__)


# Lazy initialization of BusinessLogic
class BusinessLogicManager:
    """Manages the lazy initialization and retrieval of the BusinessLogic instance for the worker."""

    _business_logic: BusinessLogic | None = None
    _lock = threading.Lock()

    @classmethod
    def get_business_logic(cls) -> BusinessLogic:
        """Get or initialize the BusinessLogic instance for the worker.

        This method is thread-safe.
        """
        if cls._business_logic is None:
            with cls._lock:
                # Double-checked locking to ensure it's created only once
                if cls._business_logic is None:
                    cls._business_logic = BusinessLogicFactory.create(loaded_config, mode="worker")
                    logger.info("BusinessLogic initialized for worker")

        if cls._business_logic is None:
            raise RuntimeError("BusinessLogic failed to initialize")

        return cls._business_logic


@celery_app.task(
    name="sync_arc_to_gitlab",
    autoretry_for=(TransientError,),
    retry_backoff=loaded_config.celery.retry_backoff,
    retry_backoff_max=loaded_config.celery.retry_backoff_max,
    retry_jitter=True,
    max_retries=loaded_config.celery.max_retries,
)
def sync_arc_to_gitlab(task: ArcSyncTask) -> None:
    """Sync ARC to GitLab asynchronously.

    This task is responsible for the slow GitLab synchronization phase.
    It is triggered by the API after the ARC has been successfully stored in CouchDB.

    Args:
        task: Validated payload for the sync task.
    """
    # Celery passes dicts after JSON deserialization
    if isinstance(task, dict):
        task = ArcSyncTask.model_validate(task)

    rdi = task.rdi
    arc_data = task.arc
    client_id = task.client_id

    logger.info("[%s] Starting GitLab sync task for RDI %s", client_id, rdi)

    try:

        async def _run_sync() -> None:
            logic = BusinessLogicManager.get_business_logic()
            async with logic:  # pylint: disable=not-async-context-manager
                await logic.sync_to_gitlab(rdi, arc_data)

        asyncio.run(_run_sync())

        logger.info("[%s] Successfully completed GitLab sync task for RDI %s", client_id, rdi)

    except Exception as e:
        logger.error("[%s] GitLab sync task failed: %s", client_id, e, exc_info=True)
        # Re-raise to mark task as failed in Celery
        raise e
