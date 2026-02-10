"""Configuration module for the Middleware API Client."""

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator

from middleware.shared.config.config_base import ConfigBase


class Config(ConfigBase):
    """Configuration model for the Middleware API Client.

    This configuration class extends ConfigBase and provides settings
    for connecting to the Middleware API with certificate-based authentication.
    """

    api_url: Annotated[str, Field(description="Base URL of the Middleware API (e.g., https://api.example.com)")]
    client_cert_path: Annotated[
        Path | None, Field(description="Path to the client certificate file in PEM format (optional)")
    ] = None
    client_key_path: Annotated[
        Path | None, Field(description="Path to the client private key file in PEM format (optional)")
    ] = None
    ca_cert_path: Annotated[
        Path | None, Field(description="Path to the CA certificate file for server verification (optional)")
    ] = None
    timeout: Annotated[float, Field(description="Request timeout in seconds", gt=0)] = 30.0
    verify_ssl: Annotated[bool, Field(description="Enable SSL certificate verification")] = True
    follow_redirects: Annotated[bool, Field(description="Follow HTTP redirects for API requests")] = True

    # Retry parameters
    max_retries: Annotated[int, Field(description="Maximum number of retries for transient HTTP errors", ge=0)] = 3
    retry_backoff_factor: Annotated[float, Field(description="Backoff factor for retries", gt=0)] = 2.0

    # Polling parameters
    polling_initial_delay: Annotated[
        float, Field(description="Initial delay in seconds between polling requests", gt=0)
    ] = 1.0
    polling_max_delay: Annotated[
        float, Field(description="Maximum delay in seconds between polling requests", gt=0)
    ] = 30.0
    polling_backoff_factor: Annotated[float, Field(description="Factor to increase delay between polls", gt=1.0)] = 1.5
    polling_timeout: Annotated[float, Field(description="Total timeout for polling in minutes", gt=0)] = 90.0

    @field_validator("api_url")
    @classmethod
    def ensure_trailing_slash(cls, v: str) -> str:
        """Ensure the API URL ends with a trailing slash."""
        if not v.endswith("/"):
            return v + "/"
        return v
