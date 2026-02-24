"""Common API components shared across versions."""

import logging
from typing import Annotated, Any, cast
from urllib.parse import unquote

from asn1crypto.core import Sequence, UTF8String  # type: ignore
from cryptography import x509
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import NameOID
from fastapi import Depends, Header, HTTPException, Request

logger = logging.getLogger(__name__)


class CommonApiDependencies:
    """Shared dependencies and helpers for all API versions."""

    def __init__(self, config):
        self.config = config

    def _validate_client_cert(self, request: Request) -> x509.Certificate | None:
        """Extract and parse client certificate from request headers."""
        if hasattr(request.state, "cert"):
            return getattr(request.state, "cert", None)

        headers = request.headers
        client_cert = headers.get("ssl-client-cert") or headers.get("X-SSL-Client-Cert")
        client_verify = headers.get("ssl-client-verify") or headers.get("X-SSL-Client-Verify", "NONE")

        if not client_cert:
            if self.config.require_client_cert:
                raise HTTPException(status_code=401, detail="Client certificate required")
            request.state.cert = None
            return None

        if client_verify != "SUCCESS":
            raise HTTPException(status_code=401, detail=f"Client certificate verification failed: {client_verify}")

        try:
            cert_pem = unquote(client_cert)
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"Certificate parsing error: {str(e)}") from e

        request.state.cert = cert
        return cert

    async def validate_client_id(self, request: Request) -> str:
        """Validate client certificate and return client ID."""
        cert = self._validate_client_cert(request)
        if cert is None:
            return "unknown"

        cn_attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not cn_attributes:
            raise HTTPException(status_code=400, detail="Certificate subject does not contain CN")
        
        return cast(str, cn_attributes[0].value)

    async def validate_content_type(self, request: Request) -> None:
        """Validate that the content-type is application/json."""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type")
            if not content_type or "application/json" not in content_type:
                raise HTTPException(status_code=415, detail="Content-Type must be application/json")

    async def validate_accept_type(self, request: Request) -> None:
        """Validate that the accept header is application/json."""
        accept = request.headers.get("accept")
        if accept and "*/*" not in accept and "application/json" not in accept:
            raise HTTPException(status_code=406, detail="Accept must be application/json")

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
                    seq = Sequence.load(der_bytes)
                    for i in range(len(seq)):
                        item = seq[i]
                        if isinstance(item, UTF8String):
                            allowed_rdis.append(item.native)
                    break
        except (ExtensionNotFound, TypeError, ValueError) as e:
            logger.warning("Error extracting RDI extension: %s", e)

        return allowed_rdis

    async def validate_rdi_authorized(self, rdi: str, request: Request) -> str:
        """Verify that the client is authorized for the given RDI."""
        # First check if RDI is known
        known_rdis = self.config.known_rdis if self.config.known_rdis else []
        if rdi not in known_rdis:
            raise HTTPException(status_code=400, detail=f"RDI '{rdi}' is not recognized.")

        # Then check authorization
        authorized_rdis = await self.get_authorized_rdis(request)
        if "*" in authorized_rdis or rdi in authorized_rdis:
            return rdi
        raise HTTPException(status_code=403, detail=f"RDI '{rdi}' not authorized.")


async def get_client_id(request: Request) -> str:
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


def get_business_logic(request: Request) -> Any:
    """Dependency to get BusinessLogic from the app state."""
    return request.app.state.business_logic


def get_common_deps(request: Request) -> Any:
    """Dependency to get CommonApiDependencies from the app state."""
    return request.app.state.common_deps
