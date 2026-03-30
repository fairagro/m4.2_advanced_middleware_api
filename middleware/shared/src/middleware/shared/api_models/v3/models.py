"""V3 API Models."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from ..common.models import ApiResponse, ArcLifecycleStatus, ArcStatus, HarvestStatus


class CreateArcRequest(BaseModel):
    """Request model for creating or updating a single ARC."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arc: Annotated[dict, Field(description="ARC definition in RO-Crate JSON format")]


class BaseStatusResponse(BaseModel):
    """Base response model for status-only API responses."""

    status: Annotated["StatusResponse", Field(description="Overall service status")]
    services: Annotated[dict[str, bool], Field(description="Dictionary of service checks")]


class StatusResponse(StrEnum):
    """Allowed status values for liveness/readiness/health responses."""

    OK = "ok"
    ERROR = "error"


class LivenessResponse(BaseStatusResponse):
    """Response model for liveness checks."""


class ReadinessResponse(BaseStatusResponse):
    """Response model for readiness checks."""


class HealthResponse(BaseStatusResponse):
    """Response model for global health checks."""


class SubmitHarvestArcRequest(BaseModel):
    """Request model for submitting an ARC within an ongoing harvest run.

    The ``rdi`` is not required here — it is resolved automatically from the
    harvest identified by the ``harvest_id`` path parameter.
    """

    arc: Annotated[
        dict,
        Field(
            description=(
                "ARC definition in RO-Crate JSON format. "
                "The RDI is taken from the harvest run identified by the path parameter."
            )
        ),
    ]


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
