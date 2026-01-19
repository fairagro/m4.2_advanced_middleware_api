"""Unit tests for shared config_base module."""

from middleware.shared.config.config_base import ConfigBase, OtelConfig


def test_config_base_creation() -> None:
    """Test creating a ConfigBase instance."""
    config = ConfigBase(log_level="INFO", otel=OtelConfig())

    assert config.log_level == "INFO"


def test_config_base_default_log_level() -> None:
    """Test ConfigBase with default log level."""
    config = ConfigBase(otel=OtelConfig())

    assert config.log_level == "INFO"  # Default log level


def test_config_base_different_log_levels() -> None:
    """Test ConfigBase with different log levels."""
    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"]
    for level in log_levels:
        config = ConfigBase(log_level=level, otel={})  # type: ignore[arg-type]
        assert config.log_level == level
