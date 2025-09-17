"""Shared fixtures for tests."""

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime
import pytest

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
