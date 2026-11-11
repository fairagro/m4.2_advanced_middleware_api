"""Health service orchestration for API liveness/readiness/global health checks."""

import asyncio
import logging

from .arc_store import ArcStore, ConsolidatedArcStore
from .business_logic.ports import BrokerHealthChecker
from .celery_integration import CeleryWorkerHealthChecker
from .config import Config
from .document_store import DocumentStore

logger = logging.getLogger(__name__)


class ApiHealthService:
    """Aggregates health checks for API endpoints."""

    def __init__(  # noqa: PLR0913 — health adapters are injected explicitly (no service locator)
        self,
        config: Config,
        broker_health_checker: BrokerHealthChecker,
        worker_health_checker: CeleryWorkerHealthChecker,
        *,
        document_store: DocumentStore,
        arc_store: ArcStore,
        consolidated_store: ConsolidatedArcStore | None = None,
    ) -> None:
        """Initialize the health service with check adapters.

        Args:
            config: API configuration (feature-toggle flags).
            broker_health_checker: Adapter to check RabbitMQ reachability.
            worker_health_checker: Adapter to check live Celery workers.
            document_store: Live document store used for CouchDB readiness
                       (application DB presence + optional re-init).
            arc_store: Live per-ARC ArcStore reused for the git-backend health check.
            consolidated_store: Optional ConsolidatedArcStore reused for its
                       health check when configured.
        """
        self._config = config
        self._broker_health_checker = broker_health_checker
        self._worker_health_checker = worker_health_checker
        self._document_store = document_store
        self._arc_store = arc_store
        self._consolidated_store = consolidated_store

    @staticmethod
    async def liveness_checks() -> dict[str, bool]:
        """Return liveness checks for the API process only."""
        return {"api_process": True}

    async def readiness_checks(self) -> dict[str, bool]:
        """Return readiness checks for direct API dependencies."""
        checks = await self.liveness_checks()

        if self._config.health_checks.readiness_check_couchdb:
            checks["couchdb_reachable"] = await self._check_couchdb()

        if self._config.health_checks.readiness_check_rabbitmq:
            checks["rabbitmq"] = self._broker_health_checker.is_healthy()

        return checks

    async def global_health_checks(self) -> dict[str, bool]:
        """Return global health checks for monitoring consumers."""
        checks = await self.readiness_checks()

        if self._config.health_checks.global_health_check_workers:
            checks["celery_workers"] = self._worker_health_checker.has_live_workers()

        if self._config.health_checks.global_health_check_git_backend:
            checks.update(await self._check_git_backends())

        return checks

    async def _check_couchdb(self) -> bool:
        """Check whether the configured CouchDB application database is available."""
        try:
            return await self._document_store.health_check()
        except Exception as e:  # noqa: BLE001
            logger.error("CouchDB document-store health check failed: %s", e)
            return False

    async def _check_git_backends(self) -> dict[str, bool]:
        """Check configured ArcStore slots when git-backend health is enabled."""
        results: dict[str, bool] = {}
        try:
            results["git_backend"] = await asyncio.to_thread(self._arc_store.check_health)
            if self._consolidated_store is not None:
                results["consolidated_store"] = await asyncio.to_thread(self._consolidated_store.check_health)
            return results
        except Exception as e:  # noqa: BLE001
            logger.error("Git backend health check failed: %s", e)
            results.setdefault("git_backend", False)
            # Config is the single source of truth for whether consol. was requested.
            if self._config.consolidated_store is not None:
                results.setdefault("consolidated_store", False)
            return results
