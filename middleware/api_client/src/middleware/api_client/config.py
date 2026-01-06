"""Configuration module for the Middleware API Client."""

from pathlib import Path
from typing import Annotated

from pydantic import Field

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
