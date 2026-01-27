"""Unit tests for sql_to_arc config module."""

from pathlib import Path

from pydantic import SecretStr

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
        db_name="test_db",
        db_user="test_user",
        db_password=SecretStr("test_password"),
        db_host="localhost",
        db_port=5432,
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        api_client=api_client_config,
        log_level="INFO",
        max_concurrent_tasks=10,
        otel=OtelConfig(),
    )

    assert config.db_name == "test_db"
    assert config.db_user == "test_user"
    assert config.db_password.get_secret_value() == "test_password"
    assert config.db_host == "localhost"
    assert config.db_port == 5432  # noqa: PLR2004
    assert config.rdi == "edaphobase"
    assert config.rdi_url == "https://edaphobase.org"
    assert config.log_level == "INFO"
    # Default is 2x max_concurrent_arc_builds (5 * 2 = 10)
    assert config.max_concurrent_tasks == 10  # noqa: PLR2004


def test_config_max_concurrent_tasks_custom() -> None:
    """Test creating a Config with custom max_concurrent_tasks."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        otel=OtelConfig(),
    )
    config = Config(
        db_name="test_db",
        db_user="test_user",
        db_password=SecretStr("test_password"),
        db_host="localhost",
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        api_client=api_client_config,
        max_concurrent_arc_builds=8,
        max_concurrent_tasks=32,
        otel=OtelConfig(),
    )
    assert config.max_concurrent_arc_builds == 8  # noqa: PLR2004
    assert config.max_concurrent_tasks == 32  # noqa: PLR2004


def test_config_with_defaults() -> None:
    """Test creating a Config with default values."""
    api_client_config = ApiClientConfig(
        api_url="https://api.example.com",
        client_cert_path=Path("/path/to/cert.pem"),
        client_key_path=Path("/path/to/key.pem"),
        otel=OtelConfig(),
    )

    config = Config(
        db_name="test_db",
        db_user="test_user",
        db_password=SecretStr("secret"),
        db_host="localhost",
        rdi="edaphobase",
        rdi_url="https://edaphobase.org",
        api_client=api_client_config,
        otel=OtelConfig(),
    )

    # Check defaults
    assert config.db_port == 5432  # Default port  # noqa: PLR2004
    # Default is 4x max_concurrent_arc_builds (5 * 4 = 20)
    assert config.max_concurrent_tasks == 20  # noqa: PLR2004
