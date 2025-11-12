"""FastAPI middleware for managing ARC (Advanced Research Context) objects.

This module provides an API class that handles HTTP requests for creating, reading,
updating and deleting ARC objects. It includes authentication via client certificates
and content type validation.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import unquote

from cryptography import x509
from cryptography.x509.oid import NameOID
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .arc_store.gitlab_api import GitlabApi
from .business_logic import BusinessLogic, InvalidJsonSemanticError
from .config import Config


class CreateOrUpdateArcsRequest(BaseModel):
    """Request model for creating or updating ARCs."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arcs: Annotated[list[Any], Field(description="List of ARC definitions")]


class Api:
    """FastAPI middleware for managing ARC (Advanced Research Context) objects.

    This class provides methods and routes for handling HTTP requests related to ARC
    objects, including authentication, content validation, and CRUD operations through
    FastAPI endpoints.
    """

    # Constants
    SUPPORTED_CONTENT_TYPE = "application/ro-crate+json"
    SUPPORTED_ACCEPT_TYPE = "application/json"

    def __init__(self, app_config: Config) -> None:
        """Initialize the API with optional configuration.

        Args:
            app_config (Config): Configuration object.

        """
        self._logger = logging.getLogger("middleware_api")
        self._config = app_config
        self._store = GitlabApi(self._config.gitlab_api)
        self._service = BusinessLogic(self._store)
        self._app = FastAPI(
            title="FAIR Middleware API",
            description="API for managing ARC (Advanced Research Context) objects",
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

    def get_business_logic(self) -> BusinessLogic:
        """Get the business logic service instance.

        Returns:
            BusinessLogic: The configured business logic service.

        """
        return self._service

    def _get_client_auth(self, request: Request) -> tuple[str, list[str]]:
        """Get client ID from certificate (mandatory mTLS).

        Also extracts all SAN fields matching the configured OID.
        """
        headers = request.headers
        self._logger.debug("Request headers: %s", dict(headers.items()))

        client_cert = headers.get("ssl-client-cert") or headers.get("X-SSL-Client-Cert")
        client_verify = headers.get("ssl-client-verify") or headers.get("X-SSL-Client-Verify", "NONE")
        self._logger.debug("Client cert header present: %s", bool(client_cert))
        self._logger.debug("Client verify status: %s", client_verify)

        if not client_cert:
            msg = "Client certificate required for access"
            self._logger.warning(msg)
            raise HTTPException(status_code=401, detail=msg)
        if client_verify != "SUCCESS":
            detail_msg = f"Client certificate verification failed: {client_verify}"
            self._logger.warning(detail_msg)
            raise HTTPException(status_code=401, detail=detail_msg)

        try:
            cert_pem = unquote(client_cert)
            self._logger.debug("URL decoded certificate: %s...", cert_pem[:100])
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            cn_attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            if not cn_attributes:
                msg = "Certificate subject does not contain Common Name (CN) attribute"
                self._logger.warning(msg)
                raise HTTPException(status_code=400, detail=msg)
            cn = cn_attributes[0].value
            self._logger.debug("Client certificate parsed, CN=%s", cn)
            allowed_rdis = self._extract_allowed_rdis(cert)
            self._logger.debug("SAN values for OID %s: %s", self._config.client_auth_oid, allowed_rdis)
            return (cast(str, cn), allowed_rdis)
        except ValueError as e:
            error_msg = f"Invalid certificate format: {str(e)}"
            self._logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg) from e
        except Exception as e:
            error_msg = f"Certificate parsing error: {str(e)}"
            self._logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg) from e

    def _extract_allowed_rdis(self, cert: x509.Certificate) -> list[str]:
        """Extract allowed RDIs from SAN OtherName fields matching the configured OID."""
        allowed_rdis = []
        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            oid = self._config.client_auth_oid
            for gn in ext.value:
                if isinstance(gn, x509.OtherName) and gn.type_id == oid:
                    try:
                        der_bytes = gn.value
                        if len(der_bytes) > 2 and der_bytes[0] == 0x0C:
                            length = der_bytes[1]
                            value_bytes = der_bytes[2:]
                            if len(value_bytes) == length:
                                allowed_rdis.append(value_bytes.decode("utf-8"))
                            else:
                                self._logger.warning("DER decoding error: length mismatch in SAN OtherName.")
                        else:
                            self._logger.warning("SAN OtherName is not a DER-encoded UTF8String.")
                    except Exception as e:
                        self._logger.warning(f"Could not decode SAN OtherName value: {e!r}")
        except x509.ExtensionNotFound:
            self._logger.warning("No SAN extension found in client certificate.")
        return allowed_rdis

    def _validate_content_type(self, request: Request) -> None:
        content_type = request.headers.get("content-type")
        if not content_type:
            msg = f"Content-Type header is missing. Expected '{self.SUPPORTED_CONTENT_TYPE}'."
            self._logger.warning(msg)
            raise HTTPException(status_code=415, detail=msg)
        if content_type != self.SUPPORTED_CONTENT_TYPE:
            msg = f"Unsupported Media Type. Supported types: '{self.SUPPORTED_CONTENT_TYPE}'."
            self._logger.warning(msg)
            raise HTTPException(status_code=415, detail=msg)

    def _validate_accept_type(self, request: Request) -> None:
        accept = request.headers.get("accept")
        if accept not in [self.SUPPORTED_ACCEPT_TYPE, "*/*"]:
            msg = f"Unsupported Response Type. Supported types: '{self.SUPPORTED_ACCEPT_TYPE}'."
            self._logger.warning(msg)
            raise HTTPException(status_code=406, detail=msg)

    def _setup_exception_handlers(self) -> None:
        @self._app.exception_handler(Exception)
        async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
            self._logger.error("Unhandled exception: %s", _exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error. Please contact support if the problem persists."},
            )

    def _setup_routes(self) -> None:
        @self._app.get("/v1/whoami")
        async def whoami(
            client_auth: Annotated[tuple[str, list[str]], Depends(self._get_client_auth)],
            business_logic: Annotated[BusinessLogic, Depends(self.get_business_logic)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> JSONResponse:
            client_id, _ = client_auth
            result = await business_logic.whoami(client_id)
            return JSONResponse(content=result.model_dump())

        @self._app.get("/v1/liveness")
        async def liveness(
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> JSONResponse:
            return JSONResponse(content={"message": "living"})

        @self._app.post("/v1/arcs")
        async def create_or_update_arcs(
            request_body: CreateOrUpdateArcsRequest,
            client_auth: Annotated[tuple[str, list[str]], Depends(self._get_client_auth)],
            business_logic: Annotated[BusinessLogic, Depends(self.get_business_logic)],
            _content_type_validated: Annotated[None, Depends(self._validate_content_type)],
            _accept_validated: Annotated[None, Depends(self._validate_accept_type)],
        ) -> JSONResponse:
            try:
                client_id, allowed_rdis = client_auth
                rdi = request_body.rdi
                if rdi in allowed_rdis:
                    result = await business_logic.create_or_update_arcs(rdi, request_body.arcs, client_id)
                    location = f"/v1/arcs/{result.arcs[0].id}" if result.arcs else ""
                    return JSONResponse(
                        content=result.model_dump(),
                        status_code=(201 if any(a.status == "created" for a in result.arcs) else 200),
                        headers={"Location": location},
                    )
                else:
                    msg = f"RDI '{rdi}' not authorized for client '{client_id}'."
                    self._logger.warning(msg)
                    raise HTTPException(status_code=403, detail=msg)
            except InvalidJsonSemanticError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e


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
