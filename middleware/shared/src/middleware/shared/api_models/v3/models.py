"""V3 API Models."""

from typing import Annotated

from pydantic import BaseModel, Field

from ..common.models import ApiResponse, ArcLifecycleStatus, ArcStatus, HarvestStatus


class CreateArcRequest(BaseModel):
    """Request model for creating or updating a single ARC."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arc: Annotated[dict, Field(description="ARC definition in RO-Crate JSON format")]


class ArcEventSummary(BaseModel):
    """Summary of an ARC event."""

    timestamp: Annotated[str, Field(description="Timestamp of the event")]
    type: Annotated[str, Field(description="Type of the event")]
    message: Annotated[str, Field(description="Event message")]


class ArcMetadata(BaseModel):
    """Metadata summary."""

    arc_hash: Annotated[str, Field(description="SHA256 hash of ARC content")]
    status: Annotated[ArcLifecycleStatus, Field(description="Current lifecycle status")]
    first_seen: Annotated[str, Field(description="First time ARC was seen")]
    last_seen: Annotated[str, Field(description="Last time ARC was seen")]


class ArcResponse(ApiResponse):
    """Result of an ARC operation, containing full details."""

    arc_id: Annotated[str, Field(description="ARC identifier")]
    status: Annotated[ArcStatus, Field(description="Status of the ARC operation")]
    metadata: Annotated[ArcMetadata, Field(description="Summary metadata")]
    events: Annotated[list[ArcEventSummary], Field(description="Summary event log")] = Field(default_factory=list)


class CreateHarvestRequest(BaseModel):
    """Request model for starting a new harvest."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    expected_datasets: Annotated[
        int | None,
        Field(description="Optional number of datasets expected to be harvested, as reported by the client."),
    ] = None


class HarvestResponse(ApiResponse):
    """Response model for harvest details."""

    harvest_id: Annotated[str, Field(description="Unique harvest identifier")]
    rdi: Annotated[str, Field(description="RDI identifier")]
    status: Annotated[HarvestStatus, Field(description="Current status")]
    started_at: Annotated[str, Field(description="Start timestamp")]
    completed_at: Annotated[str | None, Field(description="Completion timestamp")] = None
    statistics: Annotated[dict, Field(description="Harvest statistics")]
