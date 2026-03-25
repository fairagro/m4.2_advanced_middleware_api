"""Common API components shared across versions."""

import logging
from http import HTTPStatus
from typing import cast
from urllib.parse import unquote

from asn1crypto.core import SequenceOf, UTF8String  # type: ignore
from cryptography import x509
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import NameOID
from fastapi import HTTPException, Request

from middleware.api.api.legacy.task_status_store import LegacyTaskStatusStore
from middleware.api.business_logic import BusinessLogic
from middleware.api.config import Config
from middleware.api.health_service import ApiHealthService

logger = logging.getLogger(__name__)


class _RDISequence(SequenceOf):
    """ASN.1 sequence wrapper for RDI UTF8String entries."""

    _child_spec = UTF8String


class CommonApiDependencies:
    """Shared dependencies and helpers for all API versions."""

    def __init__(self, config: Config) -> None:
        """Initialize CommonApiDependencies with configuration.

        Args:
            config: Configuration object for API dependencies.
        """
        self.config = config

    def _validate_client_cert(self, request: Request) -> x509.Certificate | None:
        """Extract and parse client certificate from request headers."""
        # Use getattr to avoid MyPy errors on the untyped state object
        state_cert = getattr(request.state, "cert", None)
        if state_cert is not None:
            if isinstance(state_cert, x509.Certificate):
                return state_cert
            # Fallback for mocks/tests
            return cast(x509.Certificate, state_cert)

        headers = request.headers
        client_cert = headers.get("ssl-client-cert") or headers.get("X-SSL-Client-Cert")
        client_verify = headers.get("ssl-client-verify") or headers.get("X-SSL-Client-Verify", "NONE")

        if not client_cert:
            if self.config.require_client_cert:
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Client certificate required")
            request.state.cert = None
            return None

        if client_verify != "SUCCESS":
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail=f"Client certificate verification failed: {client_verify}"
            )

        try:
            cert_pem = unquote(client_cert)
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail=f"Certificate parsing error: {str(e)}"
            ) from e

        request.state.cert = cert
        return cert

    async def validate_client_id(self, request: Request) -> str | None:
        """Validate client certificate and return client ID."""
        cert = self._validate_client_cert(request)
        if cert is None:
            return None

        cn_attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not cn_attributes:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Certificate subject does not contain CN")

        return cast(str, cn_attributes[0].value)

    @classmethod
    async def validate_content_type(cls, request: Request) -> None:
        """Validate that the content-type is application/json."""
        if request.method in {"POST", "PUT", "PATCH"}:
            content_type = request.headers.get("content-type")
            if not content_type or "application/json" not in content_type:
                raise HTTPException(
                    status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE, detail="Content-Type must be application/json"
                )

    @classmethod
    async def validate_accept_type(cls, request: Request) -> None:
        """Validate that the accept header is application/json."""
        accept = request.headers.get("accept")
        if accept and "*/*" not in accept and "application/json" not in accept:
            raise HTTPException(status_code=HTTPStatus.NOT_ACCEPTABLE, detail="Accept must be application/json")

    def get_known_rdis(self) -> list[str]:
        """Return the list of known RDIs."""
        return self.config.known_rdis if self.config.known_rdis else []

    async def get_authorized_rdis(self, request: Request) -> list[str]:
        """Return list of RDIs the client is authorized for."""
        if not self.config.require_client_cert:
            return self.config.known_rdis if self.config.known_rdis else ["*"]

        cert = self._validate_client_cert(request)
        if cert is None:
            return []

        allowed_rdis = []
        oid = self.config.client_auth_oid
        try:
            for ext in cert.extensions:
                if ext.oid == oid:
                    der_bytes = ext.value.public_bytes()
                    seq = _RDISequence.load(der_bytes)
                    for item in seq:
                        allowed_rdis.append(item.native)
                    break
        except (ExtensionNotFound, TypeError, ValueError) as e:
            logger.warning("Error extracting RDI extension: %s", e)

        return allowed_rdis

    async def validate_rdi_authorized(self, rdi: str, request: Request) -> str:
        """Verify that the client is authorized for the given RDI."""
        # First check if RDI is known
        known_rdis = self.get_known_rdis()
        if rdi not in known_rdis:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"RDI '{rdi}' is not recognized.")

        # Then check authorization
        authorized_rdis = await self.get_authorized_rdis(request)
        if "*" in authorized_rdis or rdi in authorized_rdis:
            return rdi
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=f"RDI '{rdi}' not authorized.")


async def get_client_id(request: Request) -> str | None:
    """Dependency helper to get client ID from common dependencies."""
    deps: CommonApiDependencies = request.app.state.common_deps
    return await deps.validate_client_id(request)


async def get_content_type(request: Request) -> None:
    """Dependency helper to validate content type."""
    deps: CommonApiDependencies = request.app.state.common_deps
    await deps.validate_content_type(request)


async def get_accept_type(request: Request) -> None:
    """Dependency helper to validate accept type."""
    deps: CommonApiDependencies = request.app.state.common_deps
    await deps.validate_accept_type(request)


def get_business_logic(request: Request) -> BusinessLogic:
    """Dependency to get BusinessLogic from the app state."""
    bl = request.app.state.business_logic
    if isinstance(bl, BusinessLogic):
        return bl
    # Fallback to cast for mocks/tests without spec
    return cast(BusinessLogic, bl)


def get_common_deps(request: Request) -> CommonApiDependencies:
    """Dependency to get CommonApiDependencies from the app state."""
    deps = request.app.state.common_deps
    if isinstance(deps, CommonApiDependencies):
        return deps
    # Fallback for mocks/tests
    return cast(CommonApiDependencies, deps)


def get_health_service(request: Request) -> ApiHealthService:
    """Dependency to get ApiHealthService from app state."""
    service = request.app.state.health_service
    if isinstance(service, ApiHealthService):
        return service
    return cast(ApiHealthService, service)


def get_task_status_store(request: Request) -> LegacyTaskStatusStore:
    """Dependency to get legacy task status store from app state."""
    store = request.app.state.task_status_store
    if isinstance(store, LegacyTaskStatusStore):
        return store
    return cast(LegacyTaskStatusStore, store)
