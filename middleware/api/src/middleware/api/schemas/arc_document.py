"""ARC document schema for CouchDB."""

from datetime import datetime
from typing import Any, Annotated

from pydantic import BaseModel, Field, ConfigDict

from . import ArcLifecycleStatus, ArcEventType


class ArcEvent(BaseModel):
    """Single event in the ARC event log."""

    timestamp: Annotated[datetime, Field(description="Event timestamp")]
    type: Annotated[ArcEventType, Field(description="Event type")]
    message: Annotated[str, Field(description="Human-readable event description")]
    harvest_id: Annotated[str | None, Field(description="Associated harvest ID")] = None
    metadata: Annotated[dict[str, Any], Field(description="Additional event metadata")] = Field(
        default_factory=dict
    )


class GitMetadata(BaseModel):
    """Git-related metadata for an ARC."""

    last_commit_sha: Annotated[str | None, Field(description="Last git commit SHA")] = None
    last_push: Annotated[datetime | None, Field(description="Last successful push timestamp")] = None
    status: Annotated[str, Field(description="Git sync status (SYNCED, PENDING, FAILED)")] = "PENDING"


class ArcMetadata(BaseModel):
    """Metadata for an ARC document."""

    arc_hash: Annotated[str, Field(description="SHA256 hash of ARC content")]
    status: Annotated[ArcLifecycleStatus, Field(description="Current lifecycle status")]
    first_seen: Annotated[datetime, Field(description="First time ARC was seen")]
    last_seen: Annotated[datetime, Field(description="Last time ARC was seen")]
    last_harvest_id: Annotated[str | None, Field(description="Last harvest run that included this ARC")] = None
    missing_since: Annotated[datetime | None, Field(description="Timestamp when marked as missing")] = None
    events: Annotated[list[ArcEvent], Field(description="Event log")] = Field(default_factory=list)
    git: Annotated[GitMetadata, Field(description="Git-related metadata")] = Field(default_factory=GitMetadata)


class ArcDocument(BaseModel):
    """Complete ARC document for CouchDB storage."""

    # CouchDB fields
    doc_id: Annotated[str, Field(description="Document ID (arc_<hash>)", alias="_id")]
    doc_rev: Annotated[str | None, Field(description="CouchDB revision", alias="_rev")] = None

    # Document type for queries
    doc_type: Annotated[str, Field(description="Document type")] = "arc"

    # ARC data
    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arc_content: Annotated[dict[str, Any], Field(description="RO-Crate JSON content")]
    metadata: Annotated[ArcMetadata, Field(description="ARC metadata")]

    model_config = ConfigDict(populate_by_name=True)
