"""FAIRagro Middleware API configuration module."""

from typing import Annotated

from pydantic import Field, SecretStr

from middleware.api_client.config import Config as ApiClientConfig
from middleware.shared.config.config_base import ConfigBase


class Config(ConfigBase):
    """Configuration model for the Middleware API."""

    connection_string: Annotated[SecretStr, Field(description="Database connection string")]
    debug_limit: Annotated[
        int | None,
        Field(description="Debug limit for investigations (optional)", gt=0),
    ] = None
    rdi: Annotated[str, Field(description="RDI identifier (e.g. edaphobase)")]
    rdi_url: Annotated[str, Field(description="URL of the Source RDI (for provenance in report)")]
    batch_size: Annotated[int, Field(description="Batch size for ARC uploads", gt=0)] = 10
    max_concurrent_arc_builds: Annotated[
        int,
        Field(
            description="Maximum number of ARCs to build concurrently within a batch",
            ge=1,
        ),
    ] = 5
    api_client: Annotated[ApiClientConfig, Field(description="API Client configuration")]
