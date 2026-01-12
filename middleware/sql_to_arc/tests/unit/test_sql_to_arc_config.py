"""Unit tests for sql_to_arc config module."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from middleware.api_client.config import Config as ApiClientConfig
from middleware.sql_to_arc.config import Config


def test_config_creation() -> None:
    """Test creating a Config instance with all required fields."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
    )

    config = Config(
        db_name="test_db",
        db_user="test_user",
        db_password=SecretStr("test_password"),
        db_host="localhost",
        db_port=5432,
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        batch_size=10,
        api_client=api_client_config,
        log_level="INFO",
    )

    assert config.db_name == "test_db"
    assert config.db_user == "test_user"
    assert config.db_password.get_secret_value() == "test_password"
    assert config.db_host == "localhost"
    assert config.db_port == 5432
    assert config.rdi == "edaphobase"
    assert config.rdi_url == "https://edaphobase.org"
    assert config.batch_size == 10
    assert config.log_level == "INFO"


def test_config_with_defaults() -> None:
    """Test creating a Config with default values."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
    )

    config = Config(
        db_name="test_db",
        db_user="test_user",
        db_password=SecretStr("secret"),
        db_host="localhost",
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        api_client=api_client_config,
    )

    # Check defaults
    assert config.db_port == 5432  # Default port
    assert config.batch_size == 10  # Default batch size


def test_config_batch_size_validation() -> None:
    """Test that batch_size must be greater than 0."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
    )

    with pytest.raises(ValidationError) as exc_info:
        Config(
            db_name="test_db",
            db_user="test_user",
            db_password=SecretStr("secret"),
            db_host="localhost",
            rdi="edaphobase",
            rdi_url="https://edaphobase.org",
            batch_size=0,  # Invalid: must be > 0
            api_client=api_client_config,
        )

    # Verify the error message mentions batch_size
    assert "batch_size" in str(exc_info.value)
