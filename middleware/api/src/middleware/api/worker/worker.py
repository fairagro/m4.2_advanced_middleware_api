"""Celery worker module for asynchronous ARC processing tasks.

This module provides:
- sync_arc_to_gitlab: Celery task for synchronizing individual ARCs to GitLab asynchronously
"""

import asyncio
import logging
import threading

from middleware.api.business_logic import BusinessLogic, BusinessLogicFactory, TransientError
from middleware.api.business_logic.task_payloads import ArcSyncTask

from .celery_app import celery_app, loaded_config

# Initialize logger
logger = logging.getLogger(__name__)


class BusinessLogicManager:
    """Manages a single, long-lived BusinessLogic instance per worker process.

    Celery prefork workers execute each task in a regular (non-async) thread.
    Rather than connecting to CouchDB on every task invocation, this class
    owns a persistent event loop and a persistent CouchDB connection that are
    created once and reused across all tasks in the process lifetime.

    Thread-safety is ensured by double-checked locking during initialization.
    """

    _business_logic: BusinessLogic | None = None
    _loop: asyncio.AbstractEventLoop | None = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> tuple[BusinessLogic, asyncio.AbstractEventLoop]:
        """Return the shared BusinessLogic and event loop, initializing once if needed.

        CouchDB connection is established during the first call and then kept
        alive for the lifetime of the worker process.
        """
        if cls._business_logic is None:
            with cls._lock:
                # Double-checked locking: only the first thread initializes.
                if cls._business_logic is None:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    bl = BusinessLogicFactory.create(loaded_config, mode="worker")
                    new_loop.run_until_complete(bl.startup())
                    # Set _loop before _business_logic: the outer check uses
                    # _business_logic as the sentinel, so once it is set the
                    # _loop is guaranteed to be set too.
                    cls._loop = new_loop
                    cls._business_logic = bl
                    logger.info("BusinessLogic initialized and connected for worker process")

        bl = cls._business_logic
        loop = cls._loop
        if bl is None or loop is None:
            raise RuntimeError("BusinessLogicManager failed to initialize; this is a bug")
        return bl, loop


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
        logic, loop = BusinessLogicManager.get()
        loop.run_until_complete(logic.sync_to_gitlab(rdi, arc_data))
        logger.info("[%s] Successfully completed GitLab sync task for RDI %s", client_id, rdi)
    except Exception:
        logger.error("[%s] GitLab sync task failed for RDI %s", client_id, rdi, exc_info=True)
        raise
