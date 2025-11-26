"""FastAPI middleware for managing ARC (Advanced Research Context) objects.

This module provides an API class that handles HTTP requests for creating, reading,
updating and deleting ARC objects. It includes authentication via client certificates
and content type validation.
"""

import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Annotated, cast
from urllib.parse import unquote

from asn1crypto.core import Sequence, UTF8String  # type: ignore
from cryptography import x509
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import NameOID
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from middleware.shared.api_models.models import (
    CreateOrUpdateArcsRequest,
    CreateOrUpdateArcsResponse,
    LivenessResponse,
    WhoamiResponse,
)

from .arc_store.gitlab_api import GitlabApi
from .business_logic import BusinessLogic, InvalidJsonSemanticError
from .config import Config

try:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    __version__ = data["project"]["version"]
except (FileNotFoundError, KeyError):
    # Fallback, falls die Datei nicht gefunden wird oder die Struktur fehlt
    __version__ = "0.0.0"


loaded_config = None
if "pytest" in sys.modules:
    # pytest is executing this file during a test discovery run.
    # No config file is available, so we create a dummy config so that pytest does not fail.
    loaded_config = Config.from_data(
        {
            "log_level": "DEBUG",
            "gitlab_api": {
                "url": "https://localhost/",
                "branch": "dummy",
                "token": "dummy-token",
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
        logger.debug("API configuration: %s", self._config.model_dump())
        self._store = GitlabApi(self._config.gitlab_api)
        self._service = BusinessLogic(self._store)
        self._app = FastAPI(
            title="FAIR Middleware API",
            description="API for managing ARC (Advanced Research Context) objects",
            version=__version__,
        )
        self._setup_routes()
        self._setup_exception_handlers()

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance.

        Returns:
            FastAPI: The configured FastAPI application.

        """
        return self._app

    def _get_business_logic(self) -> BusinessLogic:
        """Get the business logic service instance.

        Returns:
            BusinessLogic: The configured business logic service.

        """
        return self._service

    @staticmethod
    def _validate_client_cert(request: Request) -> x509.Certificate:
        """Extract and parse client certificate from request headers.

        Args:
            request (Request): FastAPI request object.

        Returns:
            x509.Certificate: Parsed client certificate.
        """
        # check, if we've already cached the cert in the request state
        if hasattr(request.state, "cert") and isinstance(request.state.cert, x509.Certificate):
            return request.state.cert

        headers = request.headers
        logger.debug("Request headers: %s", dict(headers.items()))

        client_cert = headers.get("ssl-client-cert") or headers.get("X-SSL-Client-Cert")
        client_verify = headers.get("ssl-client-verify") or headers.get("X-SSL-Client-Verify", "NONE")
        logger.debug("Client cert header present: %s", bool(client_cert))
        logger.debug("Client verify status: %s", client_verify)

        if not client_cert:
            msg = "Client certificate required for access"
            logger.warning(msg)
            raise HTTPException(status_code=401, detail=msg)
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

    @classmethod
    def _validate_client_id(cls, request: Request) -> str:
        """Extract client ID from certificate Common Name (CN) attribute.

        Args:
            request (Request): FastAPI request object.

        Returns:
            str: Client identifier extracted from the certificate.
        """
        cert = cls._validate_client_cert(request)
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

    def _validate_rdi_known(self, request_body: CreateOrUpdateArcsRequest) -> str:
        known_rdis = self._get_known_rdis()
        rdi = request_body.rdi
        if rdi not in known_rdis:
            raise HTTPException(status_code=400, detail=f"RDI '{rdi}' is not recognized.")
        return cast(str, rdi)

    def _validate_rdi_authorized(self, request: Request, request_body: CreateOrUpdateArcsRequest) -> str:
        authorized_rdis = self._get_authorized_rdis(request)
        rdi = self._validate_rdi_known(request_body)
        if rdi not in authorized_rdis:
            raise HTTPException(status_code=403, detail=f"RDI '{rdi}' not authorized.")
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
        @self._app.get("/v1/whoami", response_model=WhoamiResponse)
        async def whoami(
            known_rdis: Annotated[list[str], Depends(self._get_known_rdis)],
            authorized_rdis: Annotated[list[str], Depends(self._get_authorized_rdis)],
            client_id: Annotated[str, Depends(self._validate_client_id)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> WhoamiResponse:
            logger.debug("Authorized RDIs: %s", authorized_rdis)
            logger.debug("Known RDIs: %s", known_rdis)
            accessible_rdis = list(set(authorized_rdis) & set(known_rdis))
            logger.debug("Accessible RDIs: %s", accessible_rdis)
            return WhoamiResponse(
                client_id=client_id, message="Client authenticated successfully", accessible_rdis=accessible_rdis
            )

        @self._app.get("/v1/liveness", response_model=LivenessResponse)
        async def liveness(
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> LivenessResponse:
            return LivenessResponse()

        @self._app.post("/v1/arcs", response_model=CreateOrUpdateArcsResponse)
        async def create_or_update_arcs(
            request_body: CreateOrUpdateArcsRequest,
            client_id: Annotated[str, Depends(self._validate_client_id)],
            business_logic: Annotated[BusinessLogic, Depends(self._get_business_logic)],
            _content_type_validated: Annotated[None, Depends(self._validate_content_type)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
            rdi: Annotated[str, Depends(self._validate_rdi_authorized)],
            response: Response,
        ) -> CreateOrUpdateArcsResponse:
            try:
                result = await business_logic.create_or_update_arcs(rdi, request_body.arcs, client_id)

                created_arcs = [arc for arc in result.arcs if arc.status == "created"]
                response.status_code = 201 if created_arcs else 200
                if created_arcs:
                    response.headers["Location"] = f"/v1/arcs/{created_arcs[0].id}"
                return result
            except InvalidJsonSemanticError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e


middleware_api = Api(loaded_config)
app = middleware_api.app


# # -------------------------
# # READ ARCs
# # -------------------------
# @app.get("/arcs", response_model=List[ARC])
# async def get_arcs():
#     return list(ARC_DB.values())

# @app.get("/arcs/{arc_id}")
# async def get_arc(arc_id: str, request: Request):
#     arc = ARC_DB.get(arc_id)
#     if not arc:
#         raise HTTPException(status_code=404, detail="ARC not found")
#     accept = request.headers.get("accept", "application/json")
#     return JSONResponse(content=serialize_arc(arc, accept))

# # -------------------------
# # UPDATE ARC
# # -------------------------
# @app.put("/arcs/{arc_id}")
# async def update_arc(arc_id: str, updated: ARC):
#     if arc_id not in ARC_DB:
#         raise HTTPException(status_code=404, detail="ARC not found")
#     updated.id = arc_id
#     updated.created_at = ARC_DB[arc_id]["created_at"]
#     updated.updated_at = datetime.now(UTC).isoformat() + "Z"
#     ARC_DB[arc_id] = updated.dict()
#     return updated

# @app.patch("/arcs/{arc_id}")
# async def patch_arc(arc_id: str, patch_data: dict):
#     if arc_id not in ARC_DB:
#         raise HTTPException(status_code=404, detail="ARC not found")
#     arc = ARC_DB[arc_id]
#     arc.update(patch_data)
#     arc["updated_at"] = datetime.now(UTC).isoformat() + "Z"
#     ARC_DB[arc_id] = arc
#     return arc

# # -------------------------
# # DELETE ARC
# # -------------------------
# @app.delete("/arcs/{arc_id}", status_code=204)
# async def delete_arc(arc_id: str):
#     if arc_id not in ARC_DB:
#         raise HTTPException(status_code=404, detail="ARC not found")
#     del ARC_DB[arc_id]
#     return Response(status_code=204)
