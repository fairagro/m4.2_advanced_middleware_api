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

    assert config.api_url == "https://api.example.com/"
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

    assert config.api_url == "https://api.example.com/"
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


def test_config_trailing_slash_validator() -> None:
    """Test that api_url always ends with a trailing slash."""
    # Case 1: No trailing slash provided
    config1 = Config(
        api_url="https://api.example.com",
        otel=OtelConfig(),
    )
    assert config1.api_url == "https://api.example.com/"

    # Case 2: Trailing slash already provided
    config2 = Config(
        api_url="https://api.example.com/",
        otel=OtelConfig(),
    )
    assert config2.api_url == "https://api.example.com/"


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


def test_config_polling_defaults() -> None:
    """Test default values for polling parameters."""
    config = Config(
        api_url="https://api.example.com",
        otel=OtelConfig(),
    )
    assert config.polling_initial_delay == 1.0
    assert config.polling_max_delay == 30.0  # noqa: PLR2004
    assert config.polling_backoff_factor == 1.5  # noqa: PLR2004
    assert config.polling_timeout == 90.0  #  noqa: PLR2004


def test_config_polling_validation() -> None:
    """Test validation of polling parameters."""
    with pytest.raises(ValidationError) as exc_info:
        Config(
            api_url="https://api.example.com",
            polling_initial_delay=0,  # Invalid: must be > 0
            otel=OtelConfig(),
        )
    assert "polling_initial_delay" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Config(
            api_url="https://api.example.com",
            polling_backoff_factor=1.0,  # Invalid: must be > 1.0
            otel=OtelConfig(),
        )
    assert "polling_backoff_factor" in str(exc_info.value)
