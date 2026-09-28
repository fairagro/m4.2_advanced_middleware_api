"""Configuration models for worker-related components."""

from typing import Annotated, Self

from pydantic import BaseModel, Field, SecretStr, model_validator

from middleware.api.arc_store.arc_store_config import ArcStoreConfig, ConsolidatedStoreConfig
from middleware.api.arc_store.git_repo import GitRepoConfig
from middleware.api.arc_store.resolution import validate_arc_store_config
from middleware.api.business_logic.config import HarvestConfig
from middleware.api.document_store.config import CouchDBConfig
from middleware.shared.config.config_base import ConfigBase


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

    known_rdis: Annotated[
        list[str],
        Field(description="Known RDI identifiers (used to validate GitLab topic mapping)"),
    ] = []
    arc_store: Annotated[
        ArcStoreConfig,
        Field(description="Required per-ARC ArcStore backend (git_repo | deprecated gitlab_api)"),
    ]
    consolidated_store: Annotated[
        ConsolidatedStoreConfig | None,
        Field(description="Optional consolidated catalog ArcStore (shared RDI catalog)"),
    ] = None
    couchdb: Annotated[CouchDBConfig, Field(description="CouchDB configuration")]
    celery: Annotated[CeleryConfig, Field(description="Celery configuration")]
    harvest: Annotated[HarvestConfig, Field(description="Default harvest configuration")] = HarvestConfig()

    @model_validator(mode="after")
    def validate_git_repo_rdi_gitlab_topics(self) -> Self:
        """Validate dual-slot ArcStore config and GitLab topic mapping."""
        validate_arc_store_config(self)
        if self.arc_store.git_repo is not None and self.known_rdis:
            git_repo = self.arc_store.git_repo
            validated_topics = GitRepoConfig.validate_rdi_gitlab_topics_for_known_rdis(
                self.known_rdis,
                git_repo.rdi_gitlab_topics,
            )
            self.arc_store = self.arc_store.model_copy(
                update={"git_repo": git_repo.model_copy(update={"rdi_gitlab_topics": validated_topics})}
            )
        return self
