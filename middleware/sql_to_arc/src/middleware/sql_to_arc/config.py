"""FAIRagro Middleware API configuration module."""

from typing import Annotated

from pydantic import Field, SecretStr

from middleware.shared.config.config_base import ConfigBase


class Config(ConfigBase):
    """Configuration model for the Middleware API."""

    db_name: Annotated[str, Field(description="Database name")]
    db_user: Annotated[str, Field(description="Database user")]
    db_password: Annotated[SecretStr, Field(description="Database password")]
    db_host: Annotated[str, Field(description="Database host")]
    db_port: Annotated[int, Field(description="Database port")] = 5432
