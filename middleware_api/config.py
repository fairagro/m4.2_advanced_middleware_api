import os
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field

from middleware_api.arc_store.gitlab_api import GitlabApiConfig
from middleware_api.utils.config_wrapper import ConfigWrapper


class Config(BaseModel):

    gitlab_api: Annotated[GitlabApiConfig, Field(
        description="Gitlab API config"
    )]

    @classmethod
    def from_config_wrapper(cls, wrapper: ConfigWrapper) -> "Config":
        unwrapped = wrapper.unwrap()
        return cls.model_validate(unwrapped)

    @classmethod
    def from_data(cls, data: dict) -> "Config":
        wrapper = ConfigWrapper.from_data(data)
        return cls.from_config_wrapper(wrapper)

    @classmethod
    def from_yaml_file(cls, path: Path | None = None) -> "Config":
        if path is None:
            path = Path("./config.yaml")
        wrapper = ConfigWrapper.from_yaml_file(path)
        return cls.from_config_wrapper(wrapper)

    @classmethod
    def from_env_var(cls, env_var: str = "MIDDLEWARE_API_CONFIG") -> "Config":
        value = os.environ.get(env_var)
        if value is not None:
            return cls.from_yaml_file(Path(value))
        return cls.from_yaml_file()
