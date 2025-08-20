from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime

from app.middleware_api import app
from app.arc_persistence_gitlab_api import ARCPersistenceGitlabAPI


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

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
    api = ARCPersistenceGitlabAPI("http://gitlab", "token", 1)
    api.gl = MagicMock()
    return api