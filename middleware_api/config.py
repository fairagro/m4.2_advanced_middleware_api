"""FAIRagro Middleware API configuration module."""

import logging
import os
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, Field, HttpUrl

from middleware_api.arc_store.gitlab_api import GitlabApiConfig
from middleware_api.utils.config_wrapper import ConfigWrapper


class Config(BaseModel):
    """Configuration model for the Middleware API."""

    log_level: Annotated[
        Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"], Field(description="Logging level")
    ] = "INFO"
    gitlab_api: Annotated[GitlabApiConfig, Field(description="Gitlab API config")]

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
    def from_yaml_file(cls, path: Path | None = None) -> "Config":
        """Create Config from a YAML file.

        Args:
            path (Path | None, optional): Path to the YAML config file. If None, uses
            "/run/secrets/middleware-api-config". Defaults to None. If the file does not
            exist, use a default dummy configuration and issue a warning.

        Returns:
            Config: Configuration instance.

        """
        if path is None:
            path = Path("/run/secrets/middleware-api-config")
        if path.is_file():
            wrapper = ConfigWrapper.from_yaml_file(path)
            return cls.from_config_wrapper(wrapper)
        logging.warning("Config file %s not found. Using default configuration, not suitable for production.", path)
        return cls.default()

    @classmethod
    def from_env_var(cls, env_var: str = "MIDDLEWARE_API_CONFIG") -> "Config":
        """Create Config from a YAML file specified in an environment variable.

        Args:
            env_var (str, optional): Name of the environment variable containing the
            path to the config file. Defaults to "MIDDLEWARE_API_CONFIG". If the variable
            is not set, use "/run/secrets/middleware-api-config" as config file. If the
            file does not exist, use a default dummy configuration and issue a warning.

        Returns:
            Config: Configuration instance.

        """
        value = os.environ.get(env_var)
        if value is not None:
            return cls.from_yaml_file(Path(value))
        return cls.from_yaml_file()

    @classmethod
    def default(cls) -> "Config":
        """Create a Config instance with default test values.

        Useful for testing or when you need a minimal configuration.

        Returns:
            Config: Configuration instance with sensible defaults.

        """
        return cls(
            log_level="INFO",
            gitlab_api=GitlabApiConfig(
                url=cast(HttpUrl, "https://localhost/"),
                branch="main",
                token="test-token",
                group="test-group",
            ),
        )
