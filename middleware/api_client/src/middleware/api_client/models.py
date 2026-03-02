"""Stable public types exposed by the Middleware API Client.

These types are intentionally independent of the server-side API models so
that the client's public interface remains stable across server API version
changes.  All mapping from server wire-format to these types happens inside
:class:`~middleware.api_client.ApiClient` and is not visible to consumers.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class ArcStatus(StrEnum):
    """Operation status of a single ARC submission."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REQUESTED = "requested"


class ArcLifecycleStatus(StrEnum):
    """Lifecycle status of an ARC in the system."""

    ACTIVE = "ACTIVE"
    PROCESSING = "PROCESSING"
    MISSING = "MISSING"
    DELETED = "DELETED"
    INVALID = "INVALID"


class HarvestStatus(StrEnum):
    """Status of a harvest run."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ArcEventSummary(BaseModel):
    """Summary of a single event recorded against an ARC."""

    timestamp: Annotated[str, Field(description="ISO 8601 timestamp of the event")]
    type: Annotated[str, Field(description="Event type identifier")]
    message: Annotated[str, Field(description="Human-readable event message")]


class ArcMetadata(BaseModel):
    """Metadata snapshot attached to an ARC result."""

    arc_hash: Annotated[str, Field(description="SHA-256 content hash of the ARC")]
    status: Annotated[ArcLifecycleStatus, Field(description="Lifecycle status")]
    first_seen: Annotated[str, Field(description="ISO 8601 timestamp of first submission")]
    last_seen: Annotated[str, Field(description="ISO 8601 timestamp of latest submission")]


class ArcResult(BaseModel):
    """Result returned by :meth:`~middleware.api_client.ApiClient.create_or_update_arc`.

    and :meth:`~middleware.api_client.ApiClient.submit_arc_in_harvest`.

    This is the stable, client-facing type.  The underlying server response
    model may change between server versions; the mapping layer inside
    :class:`~middleware.api_client.ApiClient` ensures this type stays
    compatible.
    """

    arc_id: Annotated[str, Field(description="ARC identifier")]
    status: Annotated[ArcStatus, Field(description="Operation status")]
    metadata: Annotated[ArcMetadata, Field(description="ARC metadata snapshot")]
    events: Annotated[list[ArcEventSummary], Field(description="Event log entries")] = Field(default_factory=list)
    message: Annotated[str, Field(description="Human-readable result message")] = ""
    client_id: Annotated[str | None, Field(description="Authenticated client identifier")] = None


class HarvestResult(BaseModel):
    """Result returned by harvest-related methods on :class:`~middleware.api_client.ApiClient`.

    This is the stable, client-facing type. See :class:`ArcResult` for
    the rationale behind keeping client types separate from server models.
    """

    harvest_id: Annotated[str, Field(description="Unique harvest run identifier")]
    rdi: Annotated[str, Field(description="RDI identifier")]
    status: Annotated[HarvestStatus, Field(description="Current harvest status")]
    started_at: Annotated[str, Field(description="ISO 8601 start timestamp")]
    completed_at: Annotated[str | None, Field(description="ISO 8601 completion timestamp")] = None
    statistics: Annotated[dict, Field(description="Harvest statistics")] = Field(default_factory=dict)
    message: Annotated[str, Field(description="Human-readable result message")] = ""
    client_id: Annotated[str | None, Field(description="Authenticated client identifier")] = None
