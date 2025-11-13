"""FAIRagro Middleware API configuration module."""

import logging
import re
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self, cast

from cryptography import x509
from pydantic import BaseModel, ConfigDict, Field, field_validator

from middleware_api.arc_store.gitlab_api import GitlabApiConfig
from middleware_api.utils.config_wrapper import ConfigWrapper


class Config(BaseModel):
    """Configuration model for the Middleware API."""

    log_level: Annotated[
        Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"], Field(description="Logging level")
    ] = "INFO"
    known_rdis: Annotated[list[str], Field(description="List of known RDI identifiers")] = []
    client_auth_oid: Annotated[x509.ObjectIdentifier, Field(description="OID for client authentication")] = (
        x509.ObjectIdentifier("1.3.6.1.4.1.64609.1.1")
    )
    gitlab_api: Annotated[GitlabApiConfig, Field(description="Gitlab API config")]

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("known_rdis")
    @classmethod
    def validate_known_rdis(cls, rdis: list[str]) -> list[str]:
        """Validate that RDI identifiers contain only allowed characters."""
        # This regex allows alphanumeric characters, underscore, hyphen, and dot.
        allowed_chars_pattern = re.compile(r"^[a-zA-Z0-9_.-]+$")
        for rdi in rdis:
            if not allowed_chars_pattern.match(rdi):
                msg = (
                    f"Invalid RDI identifier '{rdi}'. Only alphanumeric characters, hyphens, "
                    "underscores, and dots are allowed."
                )
                logging.error(msg)
                raise ValueError(msg)
        return rdis

    @field_validator("client_auth_oid", mode="before")
    @classmethod
    def parse_client_auth_oid(cls, oid: str | x509.ObjectIdentifier) -> x509.ObjectIdentifier:
        """Validate that client_auth_oid is a valid OID (e.g. 1.2.3.4.55516)."""
        if isinstance(oid, str):
            return x509.ObjectIdentifier(oid)
        return oid

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
    def from_yaml_file(cls, path: Path) -> "Config":
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
