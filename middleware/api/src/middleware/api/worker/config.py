"""Configuration models for worker-related components."""

from typing import Annotated

from pydantic import BaseModel, Field, SecretStr

from middleware.shared.config.config_base import ConfigBase

from ..arc_store.config import GitRepoConfig
from ..arc_store.gitlab_api import GitlabApiConfig
from ..business_logic.config import HarvestConfig
from ..document_store.config import CouchDBConfig


class CeleryConfig(BaseModel):
    """Configuration for Celery worker."""

    broker_url: Annotated[
        SecretStr,
        Field(description="RabbitMQ broker URL"),
    ]
    result_backend: Annotated[
        SecretStr | None,
        Field(description="[DEPRECATED] Backend URL for results", deprecated=True),
    ] = None
    task_rate_limit: Annotated[str | None, Field(description="Rate limit for tasks (e.g. '10/m')")] = None
    retry_backoff: Annotated[bool, Field(description="Whether to use exponential backoff for retries")] = True
    retry_backoff_max: Annotated[int, Field(description="Max backoff time in seconds")] = 3600
    max_retries: Annotated[int, Field(description="Max number of retries for transient errors")] = 120


class WorkerConfig(ConfigBase):
    """Worker runtime configuration projection from the shared flat config file."""

    git_repo: Annotated[GitRepoConfig | None, Field(description="GitRepo storage backend configuration")] = None
    gitlab_api: Annotated[
        GitlabApiConfig | None,
        Field(description="GitLab API storage backend configuration", deprecated=True),
    ] = None
    couchdb: Annotated[CouchDBConfig, Field(description="CouchDB configuration")]
    celery: Annotated[CeleryConfig, Field(description="Celery configuration")]
    harvest: Annotated[HarvestConfig, Field(description="Default harvest configuration")] = HarvestConfig()
