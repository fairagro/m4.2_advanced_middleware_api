"""Configuration models for document store components."""

from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, field_validator


class CouchDBConfig(BaseModel):
    """Configuration for CouchDB."""

    url: Annotated[str, Field(description="CouchDB URL")]
    user: Annotated[str | None, Field(description="CouchDB username")] = None
    password: Annotated[SecretStr | None, Field(description="CouchDB password")] = None
    db_name: Annotated[str, Field(description="Name of the database for ARCs and harvests")] = "arcs"
    max_event_log_size: Annotated[int, Field(default=100, description="Maximum number of events in ARC metadata")] = 100
    default_query_limit: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=10_000,
            description="Default maximum number of documents returned by a Mango query",
        ),
    ] = 100
    max_save_retries: Annotated[
        int,
        Field(
            default=3,
            ge=1,
            le=100,
            description="Maximum retry attempts for save_document on CouchDB revision conflicts",
        ),
    ] = 3
    pending_poll_attempts: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=10_000,
            description="Poll attempts while waiting for a pending harvest idempotency claim",
        ),
    ] = 20
    pending_poll_delay_s: Annotated[
        float,
        Field(
            default=0.05,
            ge=0.0,
            description="Delay in seconds between pending idempotency claim poll attempts",
        ),
    ] = 0.05
    catalog_list_page_size: Annotated[
        int,
        Field(
            default=500,
            ge=1,
            le=10_000,
            description="Mango page size (bookmark paging) when streaming ARC contents for catalog finalize",
        ),
    ] = 500
    catalog_finalize_lock_wait_timeout_s: Annotated[
        float,
        Field(
            default=60.0,
            ge=0.1,
            description="Max seconds to wait for the per-RDI catalog finalize claim before transient retry",
        ),
    ] = 60.0
    catalog_finalize_lock_ttl_s: Annotated[
        float,
        Field(
            default=600.0,
            ge=1.0,
            description="Stale finalize claim TTL (seconds); expired claims are stolen on wait",
        ),
    ] = 600.0
    catalog_finalize_lock_poll_delay_s: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.0,
            description="Delay between polls while waiting for a held catalog finalize claim",
        ),
    ] = 0.1

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, value: str) -> str:
        """Ensure CouchDB URL uses an explicit HTTP(S) scheme."""
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("couchdb.url must start with 'http://' or 'https://'")
        return value
