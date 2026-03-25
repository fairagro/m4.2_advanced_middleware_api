"""FAIRagro Middleware API configuration module."""

import logging
import re
import warnings
from typing import Annotated, ClassVar, Self

from cryptography import x509
from pydantic import ConfigDict, Field, field_validator, model_validator

from middleware.shared.config.config_base import ConfigBase

from .arc_store.config import GitRepoConfig
from .arc_store.gitlab_api import GitlabApiConfig
from .business_logic.config import HarvestConfig
from .document_store.config import CouchDBConfig
from .worker.config import CeleryConfig


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

    git_repo: Annotated[GitRepoConfig | None, Field(description="GitRepo storage backend configuration")] = None
    gitlab_api: Annotated[
        GitlabApiConfig | None,
        Field(description="GitLab API storage backend configuration", deprecated=True),
    ] = None
    couchdb: Annotated[CouchDBConfig, Field(description="CouchDB configuration")]

    celery: Annotated[CeleryConfig, Field(description="Celery configuration")]
    harvest: Annotated[HarvestConfig, Field(description="Default Harvest configuration")] = HarvestConfig()
    health_checks: Annotated[
        HealthCheckConfig,
        Field(description="Health check feature-toggle configuration"),
    ] = HealthCheckConfig()

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
        """Validate that exactly one backend is configured."""
        if self.git_repo is None and self.gitlab_api is None:
            raise ValueError("Either git_repo or gitlab_api must be configured")
        if self.git_repo is not None and self.gitlab_api is not None:
            raise ValueError("Only one of git_repo or gitlab_api can be configured")
        return self

    @field_validator("gitlab_api")
    @classmethod
    def warn_deprecated_gitlab_api(cls, gitlab_api: GitlabApiConfig | None) -> GitlabApiConfig | None:
        """
        Warn about the deprecation of the GitLab API configuration.

        Parameters
        ----------
        gitlab_api : GitlabApiConfig | None
            The GitLab API configuration to validate.

        Returns
        -------
        GitlabApiConfig | None
            The validated GitLab API configuration, or None if not provided.
        """
        if gitlab_api is not None:
            message = "gitlab_api configuration is deprecated; prefer git_repo instead."
            logging.warning(message)
            warnings.warn(message, DeprecationWarning, stacklevel=2)
        return gitlab_api
