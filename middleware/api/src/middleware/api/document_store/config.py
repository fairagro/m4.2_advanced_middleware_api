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
    harvest_stats_max_retries: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=100,
            description="Maximum retry attempts for atomic harvest statistics updates on CouchDB revision conflicts",
        ),
    ] = 5

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, value: str) -> str:
        """Ensure CouchDB URL uses an explicit HTTP(S) scheme."""
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("couchdb.url must start with 'http://' or 'https://'")
        return value
