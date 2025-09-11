from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from pydantic import HttpUrl
import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime

from middleware_api.api import Api
from middleware_api.business_logic import (
    ArcResponse,
    ArcStatus,
    CreateOrUpdateArcsResponse,
    BusinessLogicResponse,
    BusinessLogic
)
from middleware_api.arc_store.gitlab_api import GitlabApi, GitlabApiConfig


@pytest.fixture
def middleware_api():
    return Api()

@pytest.fixture
def client(middleware_api):
    """TestClient-Fixture und sicheres Aufräumen der Dependency-Overrides."""
    with TestClient(middleware_api.app) as c:
        yield c
    middleware_api.app.dependency_overrides.clear()

@pytest.fixture
def service() -> BusinessLogic:
    store = MagicMock()
    return BusinessLogic(store)

@pytest.fixture
def mock_service(monkeypatch):
    """Mockt get_service() vollständig, ohne MiddlewareService zu referenzieren."""

    class DummyService:
        async def whoami(self, request, client_cert, accept_type):
            return BusinessLogicResponse(client_id="TestClient", message="ok")

        async def create_or_update_arcs(self, data, client_cert, content_type, accept_type):
            return CreateOrUpdateArcsResponse(
                client_id="TestClient",
                message="ok",
                arcs=[
                    ArcResponse(id="abc123", status=ArcStatus.created, timestamp="2025-01-01T00:00:00Z")
                ]
            )

    monkeypatch.setattr("app.middleware_api.get_service", lambda: DummyService())
    return DummyService()

@pytest.fixture(scope="session")
def cert() -> str:
    """Create a self-signed client certificate for testing."""
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Some-State"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Internet Widgits Pty Ltd"),
        x509.NameAttribute(NameOID.COMMON_NAME, "TestClient"),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    ).sign(private_key, hashes.SHA256())

    # Convert to PEM format
    return cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')

@pytest.fixture
def api():
    """Erzeugt ein ARCPersistenceGitlabAPI mit gemocktem Gitlab."""
    api_config = GitlabApiConfig(
        url = HttpUrl("http://gitlab"),
        token = "token",
        group = "1",
        branch = "main"
    ) # nosec
    api = GitlabApi(api_config)
    api._gitlab = MagicMock()
    return api