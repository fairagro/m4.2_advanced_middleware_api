from typing import Annotated
from pydantic import BaseModel, Field, IPvAnyAddress

from middleware_api.arc_store.gitlab_api import GitlabApiConfig
from middleware_api.utils.config_wrapper import ConfigWrapper


class Config(BaseModel):

    listen_addr: Annotated[IPvAnyAddress, Field(
        description="Listening address of the middleware API endpoint",
        default="127.0.0.1"
    )]
    listen_port: Annotated[int, Field(
        description="Listening port of the middleware endpoint",
        default = 8000,
        ge=0,
        le=65535
    )]
    gitlab_api: Annotated[GitlabApiConfig, Field(
        description="Gitlab API config"
    )]

    @classmethod
    def from_config_wrapper(cls, wrapper: ConfigWrapper) -> "Config":
        unwrapped = wrapper.unwrap()
        return cls.model_validate(unwrapped)
