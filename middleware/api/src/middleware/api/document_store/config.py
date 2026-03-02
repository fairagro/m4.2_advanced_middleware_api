"""Configuration models for document store components."""

from typing import Annotated

from pydantic import BaseModel, Field, SecretStr


class CouchDBConfig(BaseModel):
    """Configuration for CouchDB."""

    url: Annotated[str, Field(description="CouchDB URL")]
    user: Annotated[str | None, Field(description="CouchDB username")] = None
    password: Annotated[SecretStr | None, Field(description="CouchDB password")] = None
    db_name: Annotated[str, Field(description="Name of the database for ARCs and harvests")] = "arcs"
    max_event_log_size: Annotated[int, Field(default=100, description="Maximum number of events in ARC metadata")] = 100
