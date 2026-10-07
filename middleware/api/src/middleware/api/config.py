"""FAIRagro Middleware API configuration module."""

from typing import Annotated, ClassVar, Self

from cryptography import x509
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from middleware.api.arc_store.arc_store_config import ArcStoreConfig, ConsolidatedStoreConfig
from middleware.api.arc_store.resolution import validate_arc_store_config
from middleware.api.business_logic.config import HarvestConfig
from middleware.api.document_store.config import CouchDBConfig
from middleware.api.rdi_registry import (
    RdiRegistryEntry,
    known_rdi_ids,
    validate_unique_rdi_ids,
    warn_deprecated_string_known_rdis,
)
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


class RateLimitingConfig(BaseModel):
    """Process-local per-client rate limits for harvest/ARC write POSTs."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    enabled: Annotated[
        bool,
        Field(description="Enable per-client rate limiting on harvest/ARC write POSTs."),
    ] = False
    harvest_create_per_minute: Annotated[
        int,
        Field(
            description=(
                "Max POST /v3/harvests per client per minute. Non-positive disables the harvest-create class only."
            ),
        ),
    ] = 10
    arc_submit_per_minute: Annotated[
        int,
        Field(
            description=(
                "Max ARC submit POSTs (v2/v3 arcs and harvest-scoped arcs) per client per minute. "
                "Non-positive disables the arc-submit class only."
            ),
        ),
    ] = 60
    retry_after_seconds: Annotated[
        int,
        Field(
            description=(
                "Upper bound (seconds, inclusive) for the Retry-After header on rate-limit 429 responses. "
                "The actual delay is chosen uniformly at random from 1..retry_after_seconds."
            ),
            ge=1,
        ),
    ] = 60


class Config(ConfigBase):
    """Configuration model for the Middleware API."""

    known_rdis: Annotated[
        list[RdiRegistryEntry],
        Field(
            description=(
                "Known RDIs as objects with id and optional description/url (used for Investigation "
                "Comment[RDI*] enrichment). Bare identifier strings remain accepted but are deprecated."
            ),
        ),
    ] = []
    client_auth_oid: Annotated[x509.ObjectIdentifier, Field(description="OID for client authentication")] = (
        x509.ObjectIdentifier("1.3.6.1.4.1.64609.1.1")
    )

    arc_store: Annotated[
        ArcStoreConfig,
        Field(description="Required per-ARC ArcStore backend (nested git_repo)"),
    ]
    consolidated_store: Annotated[
        ConsolidatedStoreConfig | None,
        Field(description="Optional consolidated catalog ArcStore (shared RDI catalog)"),
    ] = None
    couchdb: Annotated[CouchDBConfig, Field(description="CouchDB configuration")]

    celery: Annotated[CeleryConfig, Field(description="Celery configuration")]
    harvest: Annotated[HarvestConfig, Field(description="Default Harvest configuration")] = HarvestConfig()
    health_checks: Annotated[
        HealthCheckConfig,
        Field(description="Health check feature-toggle configuration"),
    ] = HealthCheckConfig()
    rate_limiting: Annotated[
        RateLimitingConfig,
        Field(description="Per-client rate limiting for harvest/ARC write POSTs"),
    ] = RateLimitingConfig()

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

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @field_validator("known_rdis", mode="before")
    @classmethod
    def deprecate_string_known_rdis(cls, rdis: object) -> object:
        """Keep bare-string known_rdis working while warning operators to migrate."""
        return warn_deprecated_string_known_rdis(rdis)

    @field_validator("known_rdis")
    @classmethod
    def validate_known_rdis(cls, rdis: list[RdiRegistryEntry]) -> list[RdiRegistryEntry]:
        """Reject duplicate RDI identifiers (charset checked on each entry)."""
        return validate_unique_rdi_ids(rdis)

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
    def validate_storage_backends(self) -> Self:
        """Validate dual-slot ArcStore config and GitLab topic mapping."""
        self.arc_store = validate_arc_store_config(self, known_rdis=known_rdi_ids(self.known_rdis))
        return self
