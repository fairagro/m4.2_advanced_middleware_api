"""FAIRagro Middleware API configuration module."""

import logging
import re
from typing import Annotated, ClassVar, Self

from cryptography import x509
from pydantic import ConfigDict, Field, field_validator, model_validator

from middleware.api.arc_store.arc_store_config import ArcStoreConfig, GitRepoArcStoreConfig
from middleware.api.arc_store.consolidated_git import ConsolidatedGitConfig
from middleware.api.arc_store.git_repo import GitRepoConfig
from middleware.api.arc_store.gitlab_api import GitlabApiConfig
from middleware.api.arc_store.legacy_config import (
    OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT,
    OBSOLETE_TOP_LEVEL_GIT_REPO,
    OBSOLETE_TOP_LEVEL_GITLAB_API,
)
from middleware.api.arc_store.resolution import validate_arc_store_config
from middleware.api.business_logic.config import HarvestConfig
from middleware.api.document_store.config import CouchDBConfig
from middleware.api.worker.config import CeleryConfig
from middleware.shared.config.config_base import ConfigBase


class HealthCheckConfig(ConfigBase):
    """Feature flags controlling API readiness/global health checks."""

    readiness_check_couchdb: Annotated[
        bool,
        Field(description="Whether /v3/readiness should include CouchDB reachability checks."),
    ] = True
    readiness_check_rabbitmq: Annotated[
        bool,
        Field(description="Whether /v3/readiness should include RabbitMQ reachability checks."),
    ] = True
    global_health_check_workers: Annotated[
        bool,
        Field(description="Whether /v3/health should include Celery worker liveness checks."),
    ] = True
    global_health_check_git_backend: Annotated[
        bool,
        Field(description="Whether /v3/health should include Git backend reachability checks."),
    ] = False


class Config(ConfigBase):
    """Configuration model for the Middleware API."""

    known_rdis: Annotated[list[str], Field(description="List of known RDI identifiers")] = []
    client_auth_oid: Annotated[x509.ObjectIdentifier, Field(description="OID for client authentication")] = (
        x509.ObjectIdentifier("1.3.6.1.4.1.64609.1.1")
    )

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
    harvest: Annotated[HarvestConfig, Field(description="Default Harvest configuration")] = HarvestConfig()
    health_checks: Annotated[
        HealthCheckConfig,
        Field(description="Health check feature-toggle configuration"),
    ] = HealthCheckConfig()

    max_concurrent_requests: Annotated[
        int | None,
        Field(
            description=(
                "Maximum concurrent in-flight HTTP requests per API process. Unset or <= 0 disables admission control."
            ),
        ),
    ] = None
    retry_after_seconds: Annotated[
        int,
        Field(
            description=(
                "Upper bound (seconds, inclusive) for the Retry-After header on "
                "admission-control 503 responses. The actual delay is chosen uniformly "
                "at random from 1..retry_after_seconds to spread client retries."
            ),
            ge=1,
        ),
    ] = 5

    require_client_cert: Annotated[
        bool, Field(description="Require client certificate for API access (set to false for development)")
    ] = True

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
        if isinstance(oid, x509.ObjectIdentifier):
            return oid
        raise TypeError("client_auth_oid must be a string or x509.ObjectIdentifier")

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> Self:
        """Validate storage backend and GitLab topic mapping."""
        validate_arc_store_config(self)
        # Prefer ``__dict__`` so unset deprecated top-level keys do not warn on access.
        git_repo = self.__dict__.get("git_repo")
        if git_repo is not None and self.known_rdis:
            validated_topics = GitRepoConfig.validate_rdi_gitlab_topics_for_known_rdis(
                self.known_rdis,
                git_repo.rdi_gitlab_topics,
            )
            self.git_repo = git_repo.model_copy(update={"rdi_gitlab_topics": validated_topics})
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
