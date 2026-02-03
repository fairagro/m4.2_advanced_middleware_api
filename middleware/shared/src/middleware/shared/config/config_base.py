"""FAIRagro Middleware base configuration module."""

import logging
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from pydantic import BaseModel, Field, field_validator

from .config_wrapper import ConfigWrapper

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]


class OtelConfig(BaseModel):
    """OpenTelemetry logging and tracing configuration."""

    endpoint: Annotated[
        str | None,
        Field(
            description="OpenTelemetry collector endpoint URL",
            examples=["http://signoz:4318"],
        ),
    ] = None
    log_console_spans: Annotated[
        bool,
        Field(description="Log OpenTelemetry spans to console"),
    ] = False
    log_level: Annotated[
        LogLevel,
        Field(description="Logging level for OTLP log export"),
    ] = "INFO"


class ConfigBase(BaseModel):
    """Configuration base class for the FAIRagro advanced Middleware."""

    log_level: Annotated[LogLevel, Field(description="Logging level for console/stdout logging")] = "INFO"
    otel: Annotated[
        OtelConfig,
        Field(default_factory=OtelConfig, description="OpenTelemetry configuration"),
    ]

    @field_validator("otel", mode="before")
    @classmethod
    def validate_otel(cls, v: Any) -> Any:
        """Allow None for otel and convert to empty dict for default factory."""
        if v is None:
            return {}
        return v

    @classmethod
    def from_config_wrapper(cls, wrapper: ConfigWrapper) -> Self:
        """Create Config from ConfigWrapper.

        Args:
            wrapper (ConfigWrapper): Wrapped configuration data.

        Returns:
            Self: Configuration instance.

        """
        unwrapped = wrapper.unwrap()
        # Cast to satisfy MyPy's warn_return_any=true setting
        return cast(Self, cls.model_validate(unwrapped))

    @classmethod
    def from_data(cls, data: dict) -> Self:
        """Create Config from raw data dictionary.

        Args:
            data (dict): Raw configuration data.

        Returns:
            Self: Configuration instance.

        """
        wrapper = ConfigWrapper.from_data(data)
        return cls.from_config_wrapper(wrapper)

    @classmethod
    def from_yaml_file(cls, path: Path) -> Self:
        """Create Config from a YAML file.

        Args:
            path (Path): Path to the YAML config file.

        Returns:
            Config: Configuration instance.

        Raises:
            RuntimeError: If the config file is not found.

        """
        if path.is_file():
            wrapper = ConfigWrapper.from_yaml_file(path)
            return cls.from_config_wrapper(wrapper)
        msg = f"Config file {path} not found."
        logging.error(msg)
        raise RuntimeError(msg)
