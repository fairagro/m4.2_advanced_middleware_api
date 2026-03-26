"""Health service orchestration for API liveness/readiness/global health checks."""

import asyncio
import logging
from http import HTTPStatus

import aiohttp

from .arc_store import ArcStore
from .arc_store.git_repo import GitRepo
from .arc_store.gitlab_api import GitlabApi
from .business_logic.ports import BrokerHealthChecker
from .celery_integration import CeleryWorkerHealthChecker
from .config import Config

logger = logging.getLogger(__name__)


class ApiHealthService:
    """Aggregates health checks for API endpoints."""

    def __init__(
        self,
        config: Config,
        broker_health_checker: BrokerHealthChecker,
        worker_health_checker: CeleryWorkerHealthChecker,
        arc_store: ArcStore | None = None,
    ) -> None:
        """Initialize the health service with check adapters.

        Args:
            config: API configuration (feature-toggle flags).
            broker_health_checker: Adapter to check RabbitMQ reachability.
            worker_health_checker: Adapter to check live Celery workers.
            arc_store: Existing ArcStore instance reused for the git-backend
                       health check.  When ``None`` and the git-backend check
                       is enabled, a new store is created from config (legacy
                       behaviour, wastes one ThreadPoolExecutor per call).
        """
        self._config = config
        self._broker_health_checker = broker_health_checker
        self._worker_health_checker = worker_health_checker
        self._arc_store = arc_store

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
            checks["git_backend"] = await self._check_git_backend()

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

    async def _check_git_backend(self) -> bool:
        """Check whether configured Git backend is reachable."""
        try:
            if self._arc_store is not None:
                # Reuse the already-initialised store — no new thread pool.
                return await asyncio.to_thread(self._arc_store.check_health)

            # Fallback: build a transient store from config (legacy path).
            # This creates a new ThreadPoolExecutor per call; prefer injecting
            # arc_store at construction time to avoid this.

            store: GitRepo | GitlabApi
            if self._config.git_repo is not None:
                store = GitRepo(self._config.git_repo)
            elif self._config.gitlab_api is not None:
                store = GitlabApi(self._config.gitlab_api)
            else:
                logger.error("No Git backend configured")
                return False

            result = await asyncio.to_thread(store.check_health)
            await store.shutdown()
            return result
        except Exception as e:  # noqa: BLE001
            logger.error("Git backend health check failed: %s", e)
            return False
