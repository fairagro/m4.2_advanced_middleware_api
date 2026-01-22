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
        api_client=api_client_config,
        log_level="INFO",
        otel=OtelConfig(),
    )

    assert config.connection_string.get_secret_value() == "postgresql+asyncpg://user:pass@localhost:5432/db"
    assert config.debug_limit == 5  # noqa: PLR2004
    assert config.rdi == "edaphobase"
    assert config.rdi_url == "https://edaphobase.org"
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
    assert config.debug_limit is None

