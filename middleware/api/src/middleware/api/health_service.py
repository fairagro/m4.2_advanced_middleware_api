"""Health service orchestration for API liveness/readiness/global health checks."""

import asyncio
import logging
from http import HTTPStatus

import aiohttp

from .arc_store import ArcStore
from .arc_store.factory import create_arc_stores
from .business_logic.ports import BrokerHealthChecker
from .celery_integration import CeleryWorkerHealthChecker
from .config import Config
from .document_store.couchdb import CouchDB

logger = logging.getLogger(__name__)


class ApiHealthService:
    """Aggregates health checks for API endpoints."""

    def __init__(
        self,
        config: Config,
        broker_health_checker: BrokerHealthChecker,
        worker_health_checker: CeleryWorkerHealthChecker,
        arc_store: ArcStore | None = None,
        consolidated_store: ArcStore | None = None,
    ) -> None:
        """Initialize the health service with check adapters.

        Args:
            config: API configuration (feature-toggle flags).
            broker_health_checker: Adapter to check RabbitMQ reachability.
            worker_health_checker: Adapter to check live Celery workers.
            arc_store: Existing per-ARC ArcStore reused for the git-backend
                       health check. When ``None`` and the git-backend check
                       is enabled, stores are created from config (legacy
                       behaviour, wastes one ThreadPoolExecutor per call).
            consolidated_store: Optional consolidated catalog ArcStore reused
                       for its health check when configured.
        """
        self._config = config
        self._broker_health_checker = broker_health_checker
        self._worker_health_checker = worker_health_checker
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
        """Check whether CouchDB is reachable from API."""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(str(self._config.couchdb.url)) as resp,
            ):
                return resp.status == HTTPStatus.OK
        except Exception as e:  # noqa: BLE001
            logger.error("CouchDB health check failed: %s", e)
            return False

    async def _check_git_backends(self) -> dict[str, bool]:
        """Check configured ArcStore slots when git-backend health is enabled."""
        results: dict[str, bool] = {}
        try:
            if self._arc_store is not None:
                results["git_backend"] = await asyncio.to_thread(self._arc_store.check_health)
                if self._consolidated_store is not None:
                    results["consolidated_store"] = await asyncio.to_thread(self._consolidated_store.check_health)
                return results

            # Fallback: build transient stores from config (legacy path).
            doc_store = CouchDB(self._config.couchdb)
            try:
                arc_store, consolidated_store = create_arc_stores(self._config, doc_store)
                try:
                    results["git_backend"] = await asyncio.to_thread(arc_store.check_health)
                    if consolidated_store is not None:
                        results["consolidated_store"] = await asyncio.to_thread(consolidated_store.check_health)
                    return results
                finally:
                    await arc_store.shutdown()
                    if consolidated_store is not None:
                        await consolidated_store.shutdown()
            finally:
                await doc_store.close()
        except Exception as e:  # noqa: BLE001
            logger.error("Git backend health check failed: %s", e)
            results.setdefault("git_backend", False)
            # Config is the single source of truth for whether consol. was requested.
            if self._config.consolidated_store is not None:
                results.setdefault("consolidated_store", False)
            return results
