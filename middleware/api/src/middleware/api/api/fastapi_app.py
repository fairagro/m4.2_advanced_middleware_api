"""FastAPI middleware for managing ARC (Advanced Research Context) objects.

This module provides an API class that handles HTTP requests for creating, reading,
updating and deleting ARC objects. It includes authentication via client certificates
and content type validation.
"""

import logging
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace import TracerProvider

from ..business_logic import BusinessLogicFactory
from ..business_logic.exceptions import (
    AccessDeniedError,
    BusinessLogicError,
    ConflictError,
    InvalidJsonSemanticError,
    ResourceNotFoundError,
)
from ..celery_integration import (
    CeleryBrokerHealthChecker,
    CeleryTaskDispatcher,
    CeleryWorkerHealthChecker,
    build_api_celery_app,
)
from ..config import Config
from ..health_service import ApiHealthService
from .common.dependencies import CommonApiDependencies
from .legacy.task_status_store import LegacyTaskStatusStore
from .tracing import setup_api_tracing
from .v1 import arcs as arcs_v1, system as system_v1, tasks as tasks_v1
from .v2 import arcs as arcs_v2, system as system_v2, tasks as tasks_v2
from .v3 import arcs as arcs_v3, harvests as harvests_v3, system as system_v3

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("api")
except (PackageNotFoundError, ImportError):
    # Try to read from pyproject.toml as fallback (e.g. in development if not installed)
    try:
        import tomllib

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        __version__ = data["project"]["version"]
    except (FileNotFoundError, KeyError):
        __version__ = "0.0.0"


loaded_config = None
if "pytest" in sys.modules:
    # pytest is executing this file during a test discovery run.
    # No config file is available, so we create a dummy config so that pytest does not fail.
    loaded_config = Config.from_data({
        "log_level": "DEBUG",
        "celery": {
            "broker_url": "memory://",
        },
        "couchdb": {
            "url": "http://localhost:5984",
        },
        "git_repo": {
            "url": "https://localhost/",
            "branch": "dummy",
            "group": "dummy-group",
        },
    })
else:
    # Load configuration in production mode
    config_file = Path(os.environ.get("MIDDLEWARE_API_CONFIG", "/run/secrets/middleware-api-config"))
    if config_file.is_file():
        loaded_config = Config.from_yaml_file(config_file)
    else:
        logging.getLogger("middleware_api").error(
            "Middleware API configuration file not found at %s. Exiting.", config_file
        )
        sys.exit(1)

logging.basicConfig(
    level=getattr(logging, loaded_config.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger("middleware_api")


class PollingLogFilter(logging.Filter):
    """Filter to suppress polling task status logs from uvicorn access logger."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: PLR6301
        """Suppress access logs for task status polling at INFO level.

        These logs are shown if the 'middleware_api' logger is set to DEBUG.
        """
        msg = record.getMessage()
        if "GET /v1/tasks/" in msg:
            return logging.getLogger("middleware_api").isEnabledFor(logging.DEBUG)
        return True


class Api:
    """FastAPI middleware for managing ARC (Advanced Research Context) objects.

    This class provides methods and routes for handling HTTP requests related to ARC
    objects, including authentication, content validation, and CRUD operations through
    FastAPI endpoints.
    """

    # Constants
    SUPPORTED_CONTENT_TYPE = "application/json"
    SUPPORTED_ACCEPT_TYPE = "application/json"

    def __init__(self, app_config: Config) -> None:
        """Initialize the API with optional configuration.

        Args:
            app_config (Config): Configuration object.

        """
        self._config = app_config
        api_celery_app = build_api_celery_app(self._config)
        broker_health_checker = CeleryBrokerHealthChecker(api_celery_app)
        # Initialize BusinessLogic via Factory (API mode) with Celery-backed adapters.
        self.business_logic = BusinessLogicFactory.create(
            self._config,
            mode="api",
            task_dispatcher=CeleryTaskDispatcher(api_celery_app),
            broker_health_checker=broker_health_checker,
        )
        self.task_status_store = LegacyTaskStatusStore(self.business_logic.document_store)
        self.health_service = ApiHealthService(
            config=self._config,
            broker_health_checker=broker_health_checker,
            worker_health_checker=CeleryWorkerHealthChecker(api_celery_app),
        )
        self.common_deps = CommonApiDependencies(self._config)

        self._tracer_provider: TracerProvider | None = None
        self._logger_provider: LoggerProvider | None = None

        logger.debug("API configuration: %s", self._config.model_dump())

        # Apply polling log filter to uvicorn access logger
        logging.getLogger("uvicorn.access").addFilter(PollingLogFilter())

        @asynccontextmanager
        async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
            # Initialize business logic and its stores
            try:
                try:
                    async with self.business_logic:
                        logger.info("Business logic initialized successfully")
                        yield
                    logger.info("Business logic shut down successfully")
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("An unexpected error occurred during business logic initialization")
                    raise
            finally:
                # Cleanup OTEL
                if self._tracer_provider is not None:
                    try:
                        self._tracer_provider.shutdown()
                    except (RuntimeError, ValueError, OSError) as exc:
                        logger.warning("Failed to shutdown tracer provider: %s", exc)
                if self._logger_provider is not None:
                    try:
                        self._logger_provider.shutdown()
                    except (RuntimeError, ValueError, OSError) as exc:
                        logger.warning("Failed to shutdown logger provider: %s", exc)

        self._app = FastAPI(
            title="FAIR Middleware API",
            description="API for managing ARC (Advanced Research Context) objects",
            version=__version__,
            lifespan=lifespan,
        )

        # Initialize OpenTelemetry tracing and logging
        _tracing = setup_api_tracing(self._app, self._config)
        self._tracer_provider = _tracing.tracer_provider
        self._logger_provider = _tracing.logger_provider

        # Map state for routers to access
        self._app.state.business_logic = self.business_logic
        self._app.state.task_status_store = self.task_status_store
        self._app.state.health_service = self.health_service
        self._app.state.common_deps = self.common_deps

        self._setup_routes()
        self._setup_exception_handlers()

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance.

        Returns:
            FastAPI: The configured FastAPI application.
        """
        return self._app

    def _setup_exception_handlers(self) -> None:
        @self._app.exception_handler(InvalidJsonSemanticError)
        async def invalid_json_semantic_handler(_request: Request, exc: InvalidJsonSemanticError) -> JSONResponse:
            return JSONResponse(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={"detail": str(exc)},
            )

        @self._app.exception_handler(ResourceNotFoundError)
        async def not_found_handler(_request: Request, exc: ResourceNotFoundError) -> JSONResponse:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content={"detail": str(exc)},
            )

        @self._app.exception_handler(AccessDeniedError)
        async def access_denied_handler(_request: Request, exc: AccessDeniedError) -> JSONResponse:
            return JSONResponse(
                status_code=HTTPStatus.FORBIDDEN,
                content={"detail": str(exc)},
            )

        @self._app.exception_handler(ConflictError)
        async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
            return JSONResponse(
                status_code=HTTPStatus.CONFLICT,
                content={"detail": str(exc)},
            )

        @self._app.exception_handler(BusinessLogicError)
        async def business_logic_error_handler(_request: Request, _exc: BusinessLogicError) -> JSONResponse:
            logger.error("Business logic error", exc_info=True)
            return JSONResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content={"detail": "Business logic error"},
            )

        @self._app.exception_handler(Exception)
        async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
            logger.error("Unhandled exception: %s", _exc)
            return JSONResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content={"detail": "Internal Server Error. Please contact support if the problem persists."},
            )

    def _setup_routes(self) -> None:
        """Register all API routes via versioned routers."""
        # Register V1
        self._app.include_router(system_v1.router)
        self._app.include_router(arcs_v1.router)
        self._app.include_router(tasks_v1.router)

        # Register V2
        self._app.include_router(system_v2.router)
        self._app.include_router(arcs_v2.router)
        self._app.include_router(tasks_v2.router)

        # Register V3
        self._app.include_router(system_v3.router)
        self._app.include_router(arcs_v3.router)
        self._app.include_router(harvests_v3.router)


middleware_api = Api(loaded_config)
app = middleware_api.app
