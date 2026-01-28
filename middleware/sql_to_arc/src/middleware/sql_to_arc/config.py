"""FAIRagro Middleware API configuration module."""

from typing import Annotated, Any

from pydantic import Field, SecretStr, model_validator
from pydantic_core import PydanticUndefined

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
            description="Number of parallel worker processes in the CPU pool. Recommended: (CPU cores - 1).",
            ge=1,
        ),
    ] = 5
    max_concurrent_tasks: Annotated[
        int,
        Field(
            default=PydanticUndefined,  # Satisfy mypy, validator will set the 4x default
            description=(
                "Maximum number of parallel tasks (IO + CPU). Defaults to 4x max_concurrent_arc_builds if not provided."
            ),
            ge=1,
        ),
    ]
    db_batch_size: Annotated[
        int,
        Field(
            description="Number of investigations to fetch from DB at once for processing",
            ge=1,
        ),
    ] = 100
    api_client: Annotated[ApiClientConfig, Field(description="API Client configuration")]
    max_studies: Annotated[
        int,
        Field(
            description="Maximum number of studies per investigation. Investigations exceeding this will be skipped.",
            ge=1,
        ),
    ] = 5000
    max_assays: Annotated[
        int,
        Field(
            description="Maximum number of assays per investigation. Investigations exceeding this will be skipped.",
            ge=1,
        ),
    ] = 10000
    arc_generation_timeout_minutes: Annotated[
        int,
        Field(
            description="Timeout in minutes for ARC generation. If exceeded, the investigation will be skipped.",
            ge=1,
        ),
    ] = 30

    @model_validator(mode="before")
    @classmethod
    def set_default_max_concurrent_tasks(cls, data: Any) -> Any:
        """Set default max_concurrent_tasks if not provided."""
        if isinstance(data, dict) and "max_concurrent_tasks" not in data:
            field_info = cls.model_fields.get("max_concurrent_arc_builds")
            default_max_builds = getattr(field_info, "default", 5)  # A default for the default value.
            max_builds = data.get("max_concurrent_arc_builds", default_max_builds)
            data["max_concurrent_tasks"] = int(max_builds) * 4
        return data
