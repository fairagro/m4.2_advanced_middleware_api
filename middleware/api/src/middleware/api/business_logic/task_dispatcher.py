"""Celery-based task dispatcher implementation."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from celery import Celery

from middleware.api.schemas.celery_tasks import ArcSyncTask

logger = logging.getLogger(__name__)


class CeleryTaskDispatcher:
    """Dispatcher that uses Celery to send tasks by name."""

    def __init__(self, celery_app: "Celery") -> None:
        """Initialize the Celery task dispatcher.

        Args:
            celery_app: Celery application instance for sending tasks.
        """
        self._celery_app = celery_app

    def dispatch_sync_arc(self, task: ArcSyncTask) -> None:
        """Dispatch sync_arc_to_gitlab task to Celery."""
        self._celery_app.send_task("sync_arc_to_gitlab", args=(task.model_dump(),))
