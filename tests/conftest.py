"""Shared fixtures for tests."""

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@pytest.fixture(scope="session")
def known_rdis() -> list[str]:
    """Return a list of known RDIs for testing."""
    return ["rdi-1", "rdi-2"]


@pytest.fixture(scope="session")
def oid() -> x509.ObjectIdentifier:
    """Return a test OID."""
    return x509.ObjectIdentifier("1.3.6.1.4.1.37476.1.1")


@pytest.fixture(scope="session")
def cert(oid: x509.ObjectIdentifier, known_rdis: list[str]) -> str:
    """Create a self-signed client certificate for testing."""
    # Generate private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Generate certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Some-State"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Internet Widgits Pty Ltd"),
            x509.NameAttribute(NameOID.COMMON_NAME, "TestClient"),
        ]
    )

    def to_der_utf8_string(value: str) -> bytes:
        """Convert a python string to a DER-encoded UTF8String."""
        encoded = value.encode("utf-8")
        # Tag=12 (UTF8String), Length, Value
        return b"\x0c" + len(encoded).to_bytes(1, "big") + encoded

    known_rdis_der = [x509.OtherName(oid, to_der_utf8_string(rdi)) for rdi in known_rdis]

    the_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(known_rdis_der),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Convert to PEM format
    return the_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
