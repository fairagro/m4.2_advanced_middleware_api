"""FAIRagro Middleware base configuration module."""

import logging
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, Field

from middleware.shared.config_wrapper import ConfigWrapper


class ConfigBase(BaseModel):
    """Configuration base class for the FAIRagro advanced Middleware."""

    log_level: Annotated[
        Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"], Field(description="Logging level")
    ] = "INFO"

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
    def from_yaml_file(cls, path: Path) -> Self:
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
