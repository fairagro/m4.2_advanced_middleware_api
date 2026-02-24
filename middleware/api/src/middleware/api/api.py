"""FastAPI middleware for managing ARC (Advanced Research Context) objects.

This module provides an API class that handles HTTP requests for creating, reading,
updating and deleting ARC objects. It includes authentication via client certificates
and content type validation.
"""

import logging
import os
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace import TracerProvider

from middleware.shared.tracing import initialize_logging, initialize_tracing

from .business_logic_factory import BusinessLogicFactory
from .common.dependencies import CommonApiDependencies
from .config import Config
from .tracing import instrument_app

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
    loaded_config = Config.from_data(
        {
            "log_level": "DEBUG",
            "celery": {
                "broker_url": "memory://",
                "result_backend": "cache+memory://",
            },
            "couchdb": {
                "url": "http://localhost:5984",
            },
            "gitlab_api": {
                "url": "https://localhost/",
                "branch": "dummy",
                "token": "dummy-token",  # nosec B105
                "group": "dummy-group",
            },
        }
    )
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

    def filter(self, record: logging.LogRecord) -> bool:
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
        # Initialize BusinessLogic via Factory (API mode)
        self.business_logic = BusinessLogicFactory.create(self._config, mode="api")
        self.common_deps = CommonApiDependencies(self._config)

        # Map state for routers to access
        self._app.state.business_logic = self.business_logic
        self._app.state.common_deps = self.common_deps

        self._tracer_provider: TracerProvider | None = None
        self._logger_provider: LoggerProvider | None = None

        self._setup_logging_and_tracing()
        self._setup_routes()

        logger.debug("API configuration: %s", self._config.model_dump())

        # Initialize OpenTelemetry tracing with optional OTLP endpoint
        otlp_endpoint = str(self._config.otel.endpoint) if self._config.otel.endpoint else None
        self._tracer_provider, self._tracer = initialize_tracing(
            service_name="middleware-api",
            otlp_endpoint=otlp_endpoint,
            log_console_spans=self._config.otel.log_console_spans,
        )
        # Initialize OTEL log export if configured
        self._logger_provider = initialize_logging(
            service_name="middleware-api",
            otlp_endpoint=otlp_endpoint,
            log_level=getattr(logging, self._config.log_level),
            otlp_log_level=getattr(logging, self._config.otel.log_level),
        )

        # Apply polling log filter to uvicorn access logger
        logging.getLogger("uvicorn.access").addFilter(PollingLogFilter())

        @asynccontextmanager
        async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
            # Initialize connections
            try:
                try:
                    await self.business_logic.connect()
                    logger.info("Business logic connected successfully")
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("An unexpected error occurred during business logic connection")
                    raise

                yield
            finally:
                # Cleanup
                try:
                    await self.business_logic.close()
                    logger.info("Business logic disconnected successfully")
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("An error occurred during business logic disconnection")

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

        # Instrument the FastAPI application with OpenTelemetry
        instrument_app(self._app)

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
        @self._app.exception_handler(Exception)
        async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
            logger.error("Unhandled exception: %s", _exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error. Please contact support if the problem persists."},
            )

    def _setup_routes(self) -> None:
        """Register all API routes via versioned routers."""
        from .v1 import arcs as arcs_v1, tasks as tasks_v1, system as system_v1
        from .v2 import arcs as arcs_v2, tasks as tasks_v2, system as system_v2
        from .v3 import arcs as arcs_v3, harvests as harvests_v3

        # Register V1
        self._app.include_router(system_v1.router)
        self._app.include_router(arcs_v1.router)
        self._app.include_router(tasks_v1.router)

        # Register V2
        self._app.include_router(system_v2.router)
        self._app.include_router(arcs_v2.router)
        self._app.include_router(tasks_v2.router)

        # Register V3
        self._app.include_router(arcs_v3.router)
        self._app.include_router(harvests_v3.router)


middleware_api = Api(loaded_config)
app = middleware_api.app
