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
from pathlib import Path
from typing import Annotated, cast
from urllib.parse import unquote

import redis
from asn1crypto.core import Sequence, UTF8String  # type: ignore
from cryptography import x509
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import NameOID
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace import TracerProvider
from pydantic import ValidationError

from middleware.shared.api_models.models import (
    ArcOperationResult,
    ArcTaskTicket,
    CreateOrUpdateArcRequest,
    CreateOrUpdateArcResponse,
    CreateOrUpdateArcsRequest,
    CreateOrUpdateArcsResponse,
    GetTaskStatusResponse,
    GetTaskStatusResponseV2,
    HealthResponse,
    HealthResponseV2,
    LivenessResponse,
    TaskStatus,
    WhoamiResponse,
)
from middleware.shared.tracing import initialize_logging, initialize_tracing

from .business_logic_factory import BusinessLogicFactory
from .business_logic import SetupError
from .celery_app import celery_app
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
        self._tracer_provider: TracerProvider | None = None
        self._logger_provider: LoggerProvider | None = None

        # Initialize BusinessLogic via Factory (Dispatcher mode)
        self.business_logic = BusinessLogicFactory.create(self._config, mode="dispatcher")

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
                await self.business_logic.connect()
                logger.info("Business logic connected successfully")
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("An unexpected error occurred during business logic connection")
                raise

            yield

            # Cleanup
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

    def _validate_client_cert(self, request: Request) -> x509.Certificate | None:
        """Extract and parse client certificate from request headers.

        Args:
            request (Request): FastAPI request object.

        Returns:
            x509.Certificate | None: Parsed client certificate or None if not required/provided.

        Raises:
            HTTPException: If certificate is required and missing or invalid.
        """
        # check, if we've already cached the cert in the request state
        if hasattr(request.state, "cert"):
            return getattr(request.state, "cert", None)

        headers = request.headers
        logger.debug("Request headers: %s", dict(headers.items()))

        client_cert = headers.get("ssl-client-cert") or headers.get("X-SSL-Client-Cert")
        client_verify = headers.get("ssl-client-verify") or headers.get("X-SSL-Client-Verify", "NONE")
        logger.debug("Client cert header present: %s", bool(client_cert))
        logger.debug("Client verify status: %s", client_verify)

        if not client_cert:
            if self._config.require_client_cert:
                msg = "Client certificate required for access"
                logger.warning(msg)
                raise HTTPException(status_code=401, detail=msg)
            logger.debug("Client certificate not required - proceeding without authentication")
            request.state.cert = None
            return None

        if client_verify != "SUCCESS":
            detail_msg = f"Client certificate verification failed: {client_verify}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=401, detail=detail_msg)

        try:
            cert_pem = unquote(client_cert)
            logger.debug("URL decoded certificate: %s...", cert_pem[:100])
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        except (ValueError, TypeError) as e:
            error_msg = f"Certificate parsing error: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg) from e

        request.state.cert = cert
        return cert

    def _validate_client_id(self, request: Request) -> str:
        """Extract client ID from certificate Common Name (CN) attribute.

        Args:
            request (Request): FastAPI request object.

        Returns:
            str: Client identifier extracted from the certificate, or "unknown" if not authenticated.
        """
        cert = self._validate_client_cert(request)
        if cert is None:
            logger.debug("No client certificate - client ID is unknown")
            return "unknown"

        cn_attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not cn_attributes:
            msg = "Certificate subject does not contain Common Name (CN) attribute"
            logger.warning(msg)
            raise HTTPException(status_code=400, detail=msg)
        cn = cn_attributes[0].value
        logger.debug("Client certificate parsed, CN=%s", cn)

        return cast(str, cn)

    def _get_authorized_rdis(self, request: Request) -> list[str]:
        """Extract allowed RDIs from custom extension with configured OID.

        The extension contains RDI identifiers encoded as ASN.1 SEQUENCE of UTF8Strings.
        Example: 1.3.6.1.4.1.64609.1.1 = SEQUENCE { UTF8String:"bonares", UTF8String:"edal" }
        """
        cert = self._validate_client_cert(request)
        if cert is None:
            logger.debug("No client certificate - returning empty authorized RDIs")
            return []

        oid = self._config.client_auth_oid
        allowed_rdis = self._extract_rdis_from_extension(cert, oid)

        if not allowed_rdis:
            logger.warning("No RDIs found in custom extension with OID %s", oid)

        return allowed_rdis

    @staticmethod
    def _extract_rdis_from_extension(cert: x509.Certificate, oid: x509.ObjectIdentifier) -> list[str]:
        """Extract RDI strings from certificate extension."""
        allowed_rdis = []
        try:
            for ext in cert.extensions:
                if ext.oid == oid:
                    allowed_rdis = Api._parse_rdi_sequence(ext)
                    break
        except (ExtensionNotFound, TypeError, ValueError) as e:
            logger.warning("Error extracting custom extension: %s", e)
        return allowed_rdis

    @staticmethod
    def _parse_rdi_sequence(ext: x509.Extension) -> list[str]:
        """Parse DER-encoded SEQUENCE of UTF8String RDI values."""
        rdis = []
        try:
            der_bytes = ext.value.public_bytes()
            seq = Sequence.load(der_bytes)
            # pylint: disable=consider-using-enumerate
            for i in range(len(seq)):
                item = seq[i]
                if isinstance(item, UTF8String):
                    rdis.append(item.native)
            logger.debug("Extracted RDIs from extension: %s", rdis)
        except (TypeError, ValueError) as e:
            logger.warning("Error parsing custom extension: %s", e)
        return rdis

    @staticmethod
    def _validate_content_type(request: Request) -> None:
        content_type = request.headers.get("content-type")
        if not content_type:
            msg = f"Content-Type header is missing. Expected '{Api.SUPPORTED_CONTENT_TYPE}'."
            logger.warning(msg)
            raise HTTPException(status_code=415, detail=msg)
        if content_type != Api.SUPPORTED_CONTENT_TYPE:
            msg = f"Unsupported Media Type. Supported types: '{Api.SUPPORTED_CONTENT_TYPE}'."
            logger.warning(msg)
            raise HTTPException(status_code=415, detail=msg)

    @staticmethod
    def _validate_accept_type(request: Request) -> None:
        accept = request.headers.get("accept")
        if accept not in [Api.SUPPORTED_ACCEPT_TYPE, "*/*"]:
            msg = f"Unsupported Response Type. Supported types: '{Api.SUPPORTED_ACCEPT_TYPE}'."
            logger.warning(msg)
            raise HTTPException(status_code=406, detail=msg)

    def _get_known_rdis(self) -> list[str]:
        return self._config.known_rdis

    def _validate_rdi_known(self, request_body: CreateOrUpdateArcsRequest | CreateOrUpdateArcRequest) -> str:
        known_rdis = self._get_known_rdis()
        rdi = request_body.rdi
        if rdi not in known_rdis:
            raise HTTPException(status_code=400, detail=f"RDI '{rdi}' is not recognized.")
        return cast(str, rdi)

    def _validate_rdi_authorized(
        self, request: Request, request_body: CreateOrUpdateArcsRequest | CreateOrUpdateArcRequest
    ) -> str:
        rdi = self._validate_rdi_known(request_body)

        # If client certificates are required, check authorized RDIs from certificate
        if self._config.require_client_cert:
            authorized_rdis = self._get_authorized_rdis(request)
            if rdi not in authorized_rdis:
                raise HTTPException(status_code=403, detail=f"RDI '{rdi}' not authorized.")
        else:
            # If client certificates are not required, RDI just needs to be in known_rdis
            logger.debug("Client certificates not required - RDI '%s' authorized via known_rdis", rdi)

        return cast(str, rdi)

    def _setup_exception_handlers(self) -> None:
        @self._app.exception_handler(Exception)
        async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
            logger.error("Unhandled exception: %s", _exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error. Please contact support if the problem persists."},
            )

    def _setup_routes(self) -> None:
        self._setup_whoami_route()
        self._setup_liveness_route()
        self._setup_health_route()
        self._setup_health_route_v2()
        self._setup_create_or_update_arcs_route()
        self._setup_create_or_update_arc_route_v2()
        self._setup_task_status_route()
        self._setup_task_status_route_v2()

    def _setup_whoami_route(self) -> None:
        @self._app.get("/v1/whoami", response_model=WhoamiResponse)
        async def whoami(
            known_rdis: Annotated[list[str], Depends(self._get_known_rdis)],
            authorized_rdis: Annotated[list[str], Depends(self._get_authorized_rdis)],
            client_id: Annotated[str | None, Depends(self._validate_client_id)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> WhoamiResponse:
            logger.debug("Authorized RDIs: %s", authorized_rdis)
            logger.debug("Known RDIs: %s", known_rdis)
            accessible_rdis = list(set(authorized_rdis) & set(known_rdis))
            logger.debug("Accessible RDIs: %s", accessible_rdis)
            return WhoamiResponse(
                client_id=client_id, message="Client authenticated successfully", accessible_rdis=accessible_rdis
            )

    def _setup_liveness_route(self) -> None:
        @self._app.get("/v1/liveness", response_model=LivenessResponse)
        async def liveness(
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> LivenessResponse:
            """Check if the API service is running."""
            return LivenessResponse()

    def _setup_health_route(self) -> None:
        @self._app.get("/v1/health", response_model=HealthResponse)
        async def health_check(
            response: Response,
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> HealthResponse:
            """Check health of API and connected services (Redis, RabbitMQ, CouchDB)."""
            # Check Redis (result backend)
            redis_reachable = False
            try:
                # Get Redis URL from config
                redis_url = self._config.celery.result_backend.get_secret_value()
                r = redis.from_url(redis_url)
                r.ping()
                redis_reachable = True
            except redis.RedisError as e:
                logger.error("Redis health check failed: %s", e)

            # Check RabbitMQ (broker)
            rabbitmq_reachable = False
            try:
                with celery_app.connection_or_acquire() as conn:
                    conn.ensure_connection(max_retries=1)
                    rabbitmq_reachable = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("RabbitMQ health check failed: %s", e)

            # Check BusinessLogic Dependencies (CouchDB/Dispatcher)
            # The API doesn't know what's underneath, just asks BL
            bl_health = await self.business_logic.health_check()

            # Merge statuses
            status = {"redis_reachable": redis_reachable, "rabbitmq_reachable": rabbitmq_reachable, **bl_health}

            is_healthy = all(status.values())

            if not is_healthy:
                response.status_code = 503

            return HealthResponse(
                status="ok" if is_healthy else "error",
                redis_reachable=redis_reachable,
                rabbitmq_reachable=rabbitmq_reachable,
            )

    def _setup_health_route_v2(self) -> None:
        @self._app.get("/v2/health", response_model=HealthResponseV2)
        async def health_check_v2(
            response: Response,
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> HealthResponseV2:
            """Check health of API and connected services (v2)."""
            # Check Redis
            redis_reachable = False
            try:
                redis_url = self._config.celery.result_backend.get_secret_value()
                r = redis.from_url(redis_url)
                r.ping()
                redis_reachable = True
            except Exception:  # pylint: disable=broad-exception-caught
                logger.debug("Redis health check failed")

            # Check RabbitMQ
            rabbitmq_reachable = False
            try:
                with celery_app.connection_or_acquire() as conn:
                    conn.ensure_connection(max_retries=1)
                    rabbitmq_reachable = True
            except Exception:  # pylint: disable=broad-exception-caught
                logger.debug("RabbitMQ health check failed")

            # Check BusinessLogic
            bl_health = await self.business_logic.health_check()

            services = {"redis": redis_reachable, "rabbitmq": rabbitmq_reachable, **bl_health}

            is_healthy = all(services.values())
            if not is_healthy:
                response.status_code = 503

            return HealthResponseV2(status="ok" if is_healthy else "error", services=services)

    def _setup_create_or_update_arcs_route(self) -> None:
        @self._app.post("/v1/arcs", status_code=202)
        async def create_or_update_arcs(
            request_body: CreateOrUpdateArcsRequest,
            client_id: Annotated[str, Depends(self._validate_client_id)],
            _content_type_validated: Annotated[None, Depends(self._validate_content_type)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
            rdi: Annotated[str, Depends(self._validate_rdi_authorized)],
        ) -> CreateOrUpdateArcsResponse:
            """Submit ARCs for processing asynchronously."""
            logger.info(
                "Received POST /v1/arcs request: rdi=%s, num_arcs=%d, client_id=%s",
                rdi,
                len(request_body.arcs),
                client_id,
            )

            if len(request_body.arcs) != 1:
                # For now we enforce single ARC per request as per requirements
                raise HTTPException(
                    status_code=400, detail="Currently only single ARC submission is supported per request."
                )

            # Submit task to Celery
            # We take the first (and only) ARC
            arc_data = request_body.arcs[0]

            # Use rate limiting config if available
            # Note: rate limit is usually applied at task definition or globally,
            # here we just dispatch.

            result = await self.business_logic.create_or_update_arc(rdi, arc_data, client_id)

            # Use task_id from result - we expect an ArcTaskTicket in this context
            if not isinstance(result, ArcTaskTicket):
                raise RuntimeError(f"Expected ArcTaskTicket from BusinessLogic, got {type(result)}")

            task_id = result.task_id

            logger.info("Enqueued task %s for ARC processing via BusinessLogic", task_id)

            return CreateOrUpdateArcsResponse(task_id=task_id, status="processing")

    def _setup_create_or_update_arc_route_v2(self) -> None:
        @self._app.post("/v2/arcs", status_code=202)
        async def create_or_update_arc(
            request_body: CreateOrUpdateArcRequest,
            client_id: Annotated[str, Depends(self._validate_client_id)],
            _content_type_validated: Annotated[None, Depends(self._validate_content_type)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
            rdi: Annotated[str, Depends(self._validate_rdi_authorized)],
        ) -> CreateOrUpdateArcResponse:
            """Submit a single ARC for processing asynchronously."""
            logger.info(
                "Received POST /v2/arcs request: rdi=%s, client_id=%s",
                rdi,
                client_id,
            )

            # Delegate to Business Logic (Dispatcher)
            # api.py sends arc_data. but create_or_update_arc expects 'arc' as Any.
            # The Dispatcher implementation will enqueue it.

            result = await self.business_logic.create_or_update_arc(rdi, request_body.arc, client_id)

            # Use task_id from result - we expect an ArcTaskTicket in this context
            if not isinstance(result, ArcTaskTicket):
                raise RuntimeError(f"Expected ArcTaskTicket from BusinessLogic, got {type(result)}")

            task_id = result.task_id

            logger.info("Enqueued task %s for ARC processing via BusinessLogic", task_id)

            return CreateOrUpdateArcResponse(
                task_id=task_id,
                status=TaskStatus.PENDING,
            )

    def _setup_task_status_route(self) -> None:
        @self._app.get("/v1/tasks/{task_id}")
        async def get_task_status(
            task_id: str,
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> GetTaskStatusResponse:
            """Get the status of an async task (v1)."""
            result = celery_app.AsyncResult(task_id)

            task_result: CreateOrUpdateArcsResponse | None = None
            error_message = None

            if result.ready():
                if result.successful():
                    try:
                        # Success case: result.result is a dict.
                        # Internal processing is now ArcOperationResult.
                        # We parse and transform to v1 CreateOrUpdateArcsResponse.
                        inner_res = ArcOperationResult.model_validate(result.result)
                        task_result = CreateOrUpdateArcsResponse(
                            client_id=inner_res.client_id,
                            rdi=inner_res.rdi,
                            message=inner_res.message,
                            arcs=[inner_res.arc] if inner_res.arc else [],
                        )
                    except ValidationError:
                        try:
                            # Fallback for old plural results if any exist in the backend
                            task_result = CreateOrUpdateArcsResponse.model_validate(result.result)
                        except ValidationError as e:
                            logger.error("Failed to validate task result for v1 request: %s", e)
                elif result.failed():
                    error_message = str(result.result)

            return GetTaskStatusResponse(
                task_id=task_id,
                status=result.status,
                result=task_result,
                error=error_message,
            )

    def _setup_task_status_route_v2(self) -> None:
        @self._app.get("/v2/tasks/{task_id}")
        async def get_task_status_v2(
            task_id: str,
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> GetTaskStatusResponseV2:
            """Get the status of an async task (v2)."""
            result = celery_app.AsyncResult(task_id)

            task_result: ArcOperationResult | None = None
            error_message = None

            if result.ready():
                if result.successful():
                    try:
                        task_result = ArcOperationResult.model_validate(result.result)
                    except ValidationError as e:
                        logger.error("Failed to validate task result for v2 request: %s", e)
                elif result.failed():
                    error_message = str(result.result)

            # Map Celery status to TaskStatus
            celery_status = result.status
            try:
                status = TaskStatus(celery_status)
            except ValueError:
                # Handle states not in our Enum if any (e.g. RECEIVED, RETRY handled by TaskStatus)
                status = TaskStatus.PENDING

            return GetTaskStatusResponseV2(
                status=status,
                result=task_result,
                message=error_message or "",
                client_id=task_result.client_id if task_result else None,
            )


middleware_api = Api(loaded_config)
app = middleware_api.app
