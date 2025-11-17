"""Shared fixtures for tests."""

import datetime

import pytest
from asn1crypto.core import UTF8String  # type: ignore
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
    return x509.ObjectIdentifier("1.3.6.1.4.1.64609.1.1")


@pytest.fixture(scope="session")
def cert(oid: x509.ObjectIdentifier, known_rdis: list[str]) -> str:
    """Create a self-signed client certificate with custom extension for RDIs."""
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

    # Create custom extension with RDIs as SEQUENCE of UTF8Strings
    # Build SEQUENCE manually by concatenating DER-encoded UTF8Strings
    utf8_bytes = b"".join(UTF8String(rdi).dump() for rdi in known_rdis)

    # SEQUENCE tag (0x30) + length + content
    seq_length = len(utf8_bytes)
    if seq_length < 128:
        extension_value = bytes([0x30, seq_length]) + utf8_bytes
    else:
        # Long form length encoding
        length_bytes = seq_length.to_bytes((seq_length.bit_length() + 7) // 8, "big")
        extension_value = bytes([0x30, 0x80 | len(length_bytes)]) + length_bytes + utf8_bytes

    # Create UnrecognizedExtension with the custom OID
    custom_extension = x509.UnrecognizedExtension(oid, extension_value)

    the_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .add_extension(
            custom_extension,
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Convert to PEM format
    return the_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
