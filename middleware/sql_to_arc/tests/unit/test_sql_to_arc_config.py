"""Unit tests for sql_to_arc config module."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from middleware.api_client.config import Config as ApiClientConfig
from middleware.shared.config.config_base import OtelConfig
from middleware.sql_to_arc.config import Config


def test_config_creation() -> None:
    """Test creating a Config instance with all required fields."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        otel=OtelConfig(),
    )

    config = Config(
        connection_string=SecretStr("postgresql+asyncpg://user:pass@localhost:5432/db"),
        debug_limit=5,
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        batch_size=10,
        api_client=api_client_config,
        log_level="INFO",
        otel=OtelConfig(),
    )

    assert config.connection_string.get_secret_value() == "postgresql+asyncpg://user:pass@localhost:5432/db"
    assert config.debug_limit == 5
    assert config.rdi == "edaphobase"
    assert config.rdi_url == "https://edaphobase.org"
    assert config.batch_size == 10  # noqa: PLR2004
    assert config.log_level == "INFO"


def test_config_with_defaults() -> None:
    """Test creating a Config with default values."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        otel=OtelConfig(),
    )

    config = Config(
        connection_string=SecretStr("sqlite:///:memory:"),
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        api_client=api_client_config,
        otel=OtelConfig(),
    )

    # Check defaults
    assert config.batch_size == 10  # Default batch size  # noqa: PLR2004
    assert config.debug_limit is None


def test_config_batch_size_validation() -> None:
    """Test that batch_size must be greater than 0."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        otel=OtelConfig(),
    )

    with pytest.raises(ValidationError) as exc_info:
        Config(
            connection_string=SecretStr("sqlite:///:memory:"),
            rdi="edaphobase",
            rdi_url="https://edaphobase.org",
            batch_size=0,  # Invalid: must be > 0
            api_client=api_client_config,
            otel=OtelConfig(),
        )

    # Verify the error message mentions batch_size
    assert "batch_size" in str(exc_info.value)
