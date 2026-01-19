"""Unit tests for api_client config module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from middleware.api_client.config import Config
from middleware.shared.config.config_base import OtelConfig


def test_config_creation_with_required_fields() -> None:
    """Test creating an api_client Config with required fields."""
    config = Config(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        otel=OtelConfig(),
    )

    assert config.api_url == "https://api.example.com"
    assert config.client_cert_path == Path("/path/to/cert.pem")
    assert config.client_key_path == Path("/path/to/key.pem")


def test_config_with_all_fields() -> None:
    """Test creating an api_client Config with all fields."""
    config = Config(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        ca_cert_path=Path("/path/to/ca.pem"),
        timeout=60.0,
        verify_ssl=False,
        follow_redirects=False,
        log_level="DEBUG",
        otel=OtelConfig(),
    )

    assert config.api_url == "https://api.example.com"
    assert config.ca_cert_path == Path("/path/to/ca.pem")
    assert config.timeout == 60.0  # noqa: PLR2004
    assert config.verify_ssl is False
    assert config.follow_redirects is False
    assert config.log_level == "DEBUG"


def test_config_with_defaults() -> None:
    """Test creating an api_client Config with default values."""
    config = Config(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        otel=OtelConfig(),
    )

    # Check defaults
    assert config.ca_cert_path is None
    assert config.timeout == 30.0  # noqa: PLR2004
    assert config.verify_ssl is True
    assert config.follow_redirects is True


def test_config_timeout_validation() -> None:
    """Test that timeout must be greater than 0."""
    with pytest.raises(ValidationError) as exc_info:
        Config(
            api_url="https://api.example.com",
            client_cert_path=Path("/path/to/cert.pem"),
            client_key_path=Path("/path/to/key.pem"),
            timeout=0,  # Invalid: must be > 0
            otel=OtelConfig(),
        )

    assert "timeout" in str(exc_info.value)


def test_config_timeout_negative() -> None:
    """Test that timeout cannot be negative."""
    with pytest.raises(ValidationError) as exc_info:
        Config(
            api_url="https://api.example.com",
            client_cert_path=Path("/path/to/cert.pem"),
            client_key_path=Path("/path/to/key.pem"),
            timeout=-10.0,  # Invalid: must be > 0
            otel=OtelConfig(),
        )

    assert "timeout" in str(exc_info.value)
