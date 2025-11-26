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
    client_cert_path: Annotated[str, Field(description="Path to the client certificate file in PEM format")]
    client_key_path: Annotated[str, Field(description="Path to the client private key file in PEM format")]
    ca_cert_path: Annotated[
        str | None, Field(description="Path to the CA certificate file for server verification (optional)")
    ] = None
    timeout: Annotated[float, Field(description="Request timeout in seconds", gt=0)] = 30.0
    verify_ssl: Annotated[bool, Field(description="Enable SSL certificate verification")] = True

    def get_client_cert_path(self) -> Path:
        """Get the client certificate path as a Path object.

        Returns:
            Path: Path to the client certificate file.
        """
        return Path(self.client_cert_path)

    def get_client_key_path(self) -> Path:
        """Get the client key path as a Path object.

        Returns:
            Path: Path to the client key file.
        """
        return Path(self.client_key_path)

    def get_ca_cert_path(self) -> Path | None:
        """Get the CA certificate path as a Path object.

        Returns:
            Path | None: Path to the CA certificate file, or None if not configured.
        """
        return Path(self.ca_cert_path) if self.ca_cert_path else None
