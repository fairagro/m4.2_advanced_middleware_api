"""FAIRagro Middleware API configuration module."""

import os
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field

from middleware_api.arc_store.gitlab_api import GitlabApiConfig
from middleware_api.utils.config_wrapper import ConfigWrapper


class Config(BaseModel):
    """Configuration model for the Middleware API."""

    gitlab_api: Annotated[GitlabApiConfig, Field(
        description="Gitlab API config"
    )]

    @classmethod
    def from_config_wrapper(cls, wrapper: ConfigWrapper) -> "Config":
        """Create Config from ConfigWrapper.

        Args:
            wrapper (ConfigWrapper): Wrapped configuration data.

        Returns:
            Config: Configuration instance.

        """
        unwrapped = wrapper.unwrap()
        return cls.model_validate(unwrapped)

    @classmethod
    def from_data(cls, data: dict) -> "Config":
        """Create Config from raw data dictionary.

        Args:
            data (dict): Raw configuration data.

        Returns:
            Config: Configuration instance.

        """
        wrapper = ConfigWrapper.from_data(data)
        return cls.from_config_wrapper(wrapper)

    @classmethod
    def from_yaml_file(cls, path: Path | None = None) -> "Config":
        """Create Config from a YAML file.

        Args:
            path (Path | None, optional): Path to the YAML config file. If None, uses
            "./config.yaml". Defaults to None.

        Returns:
            Config: Configuration instance.

        """
        if path is None:
            path = Path("./config.yaml")
        wrapper = ConfigWrapper.from_yaml_file(path)
        return cls.from_config_wrapper(wrapper)

    @classmethod
    def from_env_var(cls, env_var: str = "MIDDLEWARE_API_CONFIG") -> "Config":
        """Create Config from a YAML file specified in an environment variable.

        Args:
            env_var (str, optional): Name of the environment variable containing the
            path to the config file. Defaults to "MIDDLEWARE_API_CONFIG".

        Returns:
            Config: Configuration instance.

        """
        value = os.environ.get(env_var)
        if value is not None:
            return cls.from_yaml_file(Path(value))
        return cls.from_yaml_file()
