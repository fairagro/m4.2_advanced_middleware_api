"""V2 API Models."""

from typing import Annotated

from pydantic import BaseModel, Field

from ..common.models import ApiResponse, ArcOperationResult, ArcResponse, TaskStatus


class HealthResponse(BaseModel):
    """Response model for health check v2."""

    status: Annotated[str, Field(description="Overall service status (ok/error)")] = "ok"
    services: Annotated[dict[str, bool], Field(description="Dictionary of service statuses")]


class CreateOrUpdateArcRequest(BaseModel):
    """Request model for creating or updating a single ARC."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arc: Annotated[dict, Field(description="ARC definition in RO-Crate JSON format")]


class CreateOrUpdateArcResponse(ApiResponse):
    """Response model for create or update a single ARC operation ticket."""

    task_id: Annotated[str, Field(description="The ID of the background task")]
    status: Annotated[TaskStatus, Field(description="The status of the task")]


class GetTaskStatusResponse(ApiResponse):
    """Response model for task status."""

    status: Annotated[TaskStatus, Field(description="The status of the task")]
    result: Annotated[
        ArcOperationResult | None,
        Field(description="The result of the task if completed"),
    ] = None
