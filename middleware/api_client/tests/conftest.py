"""Shared test fixtures for API client tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_cert_pem(temp_dir: Path) -> tuple[Path, Path]:
    """Generate a test certificate and key in PEM format.

    Returns:
        Tuple of (cert_path, key_path)
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Generate self-signed certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test-State"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Organization"),
            x509.NameAttribute(NameOID.COMMON_NAME, "TestClient"),
        ]
    )

    import datetime

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    # Write certificate to file
    cert_path = temp_dir / "test-cert.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    # Write private key to file
    key_path = temp_dir / "test-key.pem"
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    return cert_path, key_path


@pytest.fixture
def test_config_dict(test_cert_pem: tuple[Path, Path]) -> dict:
    """Create a test configuration dictionary.

    Args:
        test_cert_pem: Tuple of (cert_path, key_path)

    Returns:
        Dictionary with test configuration
    """
    cert_path, key_path = test_cert_pem
    return {
        "log_level": "DEBUG",
        "api_url": "https://test-api.example.com",
        "client_cert_path": str(cert_path),
        "client_key_path": str(key_path),
        "timeout": "30.0",  # ConfigWrapper requires string values
        "verify_ssl": "true",  # ConfigWrapper requires string values
    }


@pytest.fixture
def test_config_yaml(temp_dir: Path, test_config_dict: dict) -> Path:
    """Create a test configuration YAML file.

    Args:
        temp_dir: Temporary directory
        test_config_dict: Configuration dictionary

    Returns:
        Path to the YAML configuration file
    """
    import yaml

    config_path = temp_dir / "test_config.yaml"
    with config_path.open("w") as f:
        yaml.dump(test_config_dict, f)

    return config_path
