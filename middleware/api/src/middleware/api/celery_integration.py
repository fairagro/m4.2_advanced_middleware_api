"""Celery integration adapters for API-side port wiring."""

import logging

from celery import Celery

from .business_logic.ports import BrokerHealthChecker
from .business_logic.task_payloads import ArcSyncTask
from .config import Config

logger = logging.getLogger(__name__)


def build_api_celery_app(config: Config) -> Celery:
    """Build a Celery client for API-side broker/task-status interactions."""
    broker_url = config.celery.broker_url.get_secret_value()
    return Celery("middleware_api", broker=broker_url)


class CeleryTaskDispatcher:
    """Dispatcher that sends ARC sync tasks to Celery by task name."""

    def __init__(self, celery_app: Celery) -> None:
        """Initialize dispatcher with Celery app instance."""
        self._celery_app = celery_app

    def dispatch_sync_arc(self, task: ArcSyncTask) -> None:
        """Dispatch sync_arc_to_gitlab task to Celery."""
        self._celery_app.send_task("sync_arc_to_gitlab", args=(task.model_dump(),))


class CeleryBrokerHealthChecker(BrokerHealthChecker):
    """Broker health checker adapter backed by Celery connection handling."""

    def __init__(self, celery_app: Celery) -> None:
        """Initialize checker with Celery app instance."""
        self._celery_app = celery_app

    def is_healthy(self) -> bool:
        """Check broker reachability via Celery connection."""
        try:
            with self._celery_app.connection_or_acquire() as conn:
                conn.ensure_connection(max_retries=1)
                return True
        except Exception as e:  # noqa: BLE001
            logger.error("RabbitMQ health check failed: %s", e)
            return False


class CeleryWorkerHealthChecker:
    """Checker for live Celery worker nodes from the API side."""

    def __init__(self, celery_app: Celery, inspect_timeout_seconds: float = 2.0) -> None:
        """Initialize checker with Celery app instance."""
        self._celery_app = celery_app
        self._inspect_timeout_seconds = inspect_timeout_seconds

    def has_live_workers(self) -> bool:
        """Return whether at least one Celery worker responds to ping."""
        try:
            inspector = self._celery_app.control.inspect(timeout=self._inspect_timeout_seconds)
            response = inspector.ping()
            return bool(response)
        except Exception as e:  # noqa: BLE001
            logger.error("Celery worker ping failed: %s", e)
            return False
