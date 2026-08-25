"""Configuration models for worker-related components."""

from typing import Annotated, Self

from pydantic import BaseModel, Field, SecretStr, model_validator

from middleware.shared.config.config_base import ConfigBase

from ..arc_store.arc_store_config import ArcStoreConfig, GitRepoArcStoreConfig
from ..arc_store.config import GitRepoConfig
from ..arc_store.consolidated_git_config import ConsolidatedGitConfig
from ..arc_store.gitlab_api import GitlabApiConfig
from ..arc_store.legacy_config import (
    OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT,
    OBSOLETE_TOP_LEVEL_GIT_REPO,
    OBSOLETE_TOP_LEVEL_GITLAB_API,
)
from ..arc_store.resolution import validate_arc_store_config
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

    known_rdis: Annotated[
        list[str],
        Field(description="Known RDI identifiers (used to validate GitLab topic mapping)"),
    ] = []
    git_repo: Annotated[
        GitRepoConfig | None,
        Field(
            description="[Obsolete] GitRepo storage backend; use arc_store.type instead",
            deprecated=OBSOLETE_TOP_LEVEL_GIT_REPO,
        ),
    ] = None
    gitlab_api: Annotated[
        GitlabApiConfig | None,
        Field(
            description="[Obsolete] GitLab API storage backend; use arc_store.type instead",
            deprecated=OBSOLETE_TOP_LEVEL_GITLAB_API,
        ),
    ] = None
    consolidated_git: Annotated[
        ConsolidatedGitConfig | None,
        Field(
            description="[Obsolete] Consolidated catalog ArcStore; use arc_store.type instead",
            deprecated=OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT,
        ),
    ] = None
    arc_store: Annotated[
        ArcStoreConfig | None,
        Field(description="Preferred ArcStore backend selector (type + nested settings)"),
    ] = None
    couchdb: Annotated[CouchDBConfig, Field(description="CouchDB configuration")]
    celery: Annotated[CeleryConfig, Field(description="Celery configuration")]
    harvest: Annotated[HarvestConfig, Field(description="Default harvest configuration")] = HarvestConfig()

    @model_validator(mode="after")
    def validate_git_repo_rdi_gitlab_topics(self) -> Self:
        """Validate ArcStore backend exclusivity and GitLab topic mapping."""
        validate_arc_store_config(self)
        if self.git_repo is not None and self.known_rdis:
            validated_topics = GitRepoConfig.validate_rdi_gitlab_topics_for_known_rdis(
                self.known_rdis,
                self.git_repo.rdi_gitlab_topics,
            )
            self.git_repo = self.git_repo.model_copy(update={"rdi_gitlab_topics": validated_topics})
        if isinstance(self.arc_store, GitRepoArcStoreConfig) and self.known_rdis:
            git_repo = self.arc_store.git_repo
            validated_topics = GitRepoConfig.validate_rdi_gitlab_topics_for_known_rdis(
                self.known_rdis,
                git_repo.rdi_gitlab_topics,
            )
            self.arc_store = self.arc_store.model_copy(
                update={"git_repo": git_repo.model_copy(update={"rdi_gitlab_topics": validated_topics})}
            )
        return self
