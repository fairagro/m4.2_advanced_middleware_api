# import os
# from pathlib import Path
from typing import Annotated
# from prettyconf import Configuration
# from prettyconf.loaders import Environment, IniFile
from pydantic import BaseModel, Field, IPvAnyAddress

from middleware_api.arc_store.gitlab_api import GitlabApiConfig


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

    # @classmethod
    # def load(cls):

    #     config_file = Path(os.getenv("MIDDLEWARE_CONFIG", "config.ini"))
    #     if config_file.absolute:
    #         config_path = config_file
    #     else:
    #         config_path = Path(__file__).parent.parent / config_file
    #     config = Configuration(loaders=[
    #         Environment(var_format=str.upper), IniFile(config_path)])

    #     # Normal
    #     self.host = config("API_HOST", default="127.0.0.1")
    #     self.port = config("API_PORT", cast=int, default=8000)

    #     # Secrets
    #     self.gitlab_url = config("GITLAB_URL")
    #     self.gitlab_token = config("GITLAB_TOKEN")
    #     self.gitlab_project_id = config("GITLAB_PROJECT_ID", cast=int)

    # def __repr__(self):
    #     return (
    #         f"Config(host={self.host}, port={self.port}, "
    #         f"gitlab_url={self.gitlab_url}, gitlab_project_id={self.gitlab_project_id})"
    #     )
