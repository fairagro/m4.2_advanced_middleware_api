"""FAIRagro Middleware API configuration module."""

from typing import Annotated

from pydantic import Field, SecretStr

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
    rdi_url: Annotated[str, Field(description="URL of the Source RDI (for provenance in report)")]
    max_concurrent_arc_builds: Annotated[
        int,
        Field(
            description="Maximum number of ARCs to build concurrently within a batch",
            ge=1,
        ),
    ] = 5
    db_batch_size: Annotated[
        int,
        Field(
            description="Number of investigations to fetch from DB at once for processing",
            ge=1,
        ),
    ] = 100
    api_client: Annotated[ApiClientConfig, Field(description="API Client configuration")]
