"""FAIRagro Middleware API configuration module."""

from typing import Annotated

from pydantic import Field, HttpUrl, SecretStr

from middleware.api_client.config import Config as ApiClientConfig
from middleware.shared.config.config_base import ConfigBase


class Config(ConfigBase):
    """Configuration model for the Middleware API."""

    db_name: Annotated[str, Field(description="Database name")]
    db_user: Annotated[str, Field(description="Database user")]
    db_password: Annotated[SecretStr, Field(description="Database password")]
    db_host: Annotated[str, Field(description="Database host")]
    db_port: Annotated[int, Field(description="Database port")] = 5432
    rdi: Annotated[str, Field(description="RDI identifier (e.g. edaphobase)")]
    batch_size: Annotated[int, Field(description="Batch size for ARC uploads", gt=0)] = 10
    api_client: Annotated[ApiClientConfig, Field(description="API Client configuration")]
    otel_endpoint: Annotated[
        HttpUrl | None,
        Field(
            description=(
                "OpenTelemetry OTLP endpoint URL (e.g. http://signoz:4318 for Signoz). "
                "If not set, traces will only be logged to console."
            )
        ),
    ] = None
