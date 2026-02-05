"""FAIRagro Middleware API configuration module."""

import logging
import re
from typing import Annotated, ClassVar, Self

from cryptography import x509
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from middleware.shared.config.config_base import ConfigBase

from .arc_store.git_repo import GitRepoConfig
from .arc_store.gitlab_api import GitlabApiConfig


class CeleryConfig(BaseModel):
    """Configuration for Celery worker."""

    broker_url: Annotated[SecretStr, Field(description="RabbitMQ broker URL")]
    result_backend: Annotated[SecretStr, Field(description="Redis backend URL")]
    task_rate_limit: Annotated[str | None, Field(description="Rate limit for tasks (e.g. '10/m')")] = None


class CouchDBConfig(BaseModel):
    """Configuration for CouchDB."""

    url: Annotated[str, Field(description="CouchDB URL")] = "http://localhost:5984"
    user: Annotated[str | None, Field(description="CouchDB username")] = None
    password: Annotated[
        SecretStr | None, Field(description="CouchDB password")
    ] = None
    db_name: Annotated[str, Field(description="Name of the database to store ARCs in")] = "arcs"


class Config(ConfigBase):
    """Configuration model for the Middleware API."""

    known_rdis: Annotated[list[str], Field(description="List of known RDI identifiers")] = []
    client_auth_oid: Annotated[x509.ObjectIdentifier, Field(description="OID for client authentication")] = (
        x509.ObjectIdentifier("1.3.6.1.4.1.64609.1.1")
    )

    git_repo: Annotated[GitRepoConfig | None, Field(description="GitRepo storage backend configuration")] = None
    gitlab_api: Annotated[GitlabApiConfig | None, Field(description="GitLab API storage backend configuration")] = None
    couchdb: Annotated[CouchDBConfig, Field(default_factory=CouchDBConfig, description="CouchDB configuration")]

    celery: Annotated[CeleryConfig, Field(description="Celery configuration")]

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
