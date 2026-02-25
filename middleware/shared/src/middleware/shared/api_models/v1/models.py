"""V1 API Models."""

from typing import Annotated

from pydantic import BaseModel, Field

from ..common.models import ApiResponse, ArcResponse


class LivenessResponse(BaseModel):
    """Response model for liveness check."""

    message: Annotated[str, Field(description="Liveness message")] = "ok"


class HealthResponse(BaseModel):
    """Response model for health check including backend status."""

    status: Annotated[str, Field(description="Overall service status (ok/error)")] = "ok"
    redis_reachable: Annotated[
        bool,
        Field(
            description="[DEPRECATED] Kept for backward compatibility. Always True as Redis is no longer used.",
            deprecated=True,
        ),
    ] = True
    rabbitmq_reachable: Annotated[bool, Field(description="True if RabbitMQ is reachable")]


class WhoamiResponse(ApiResponse):
    """Response model for whoami operation."""

    accessible_rdis: Annotated[
        list[str], Field(description="List of Research Data Infrastructures the client is authorized for")
    ]


class ArcTaskTicket(ApiResponse):
    """Response model for a newly created async task ticket."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier the ARC belongs to")]
    task_id: Annotated[str, Field(description="Async task ID")]


class CreateOrUpdateArcsRequest(BaseModel):
    """Request model for creating or updating ARCs."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arcs: Annotated[list[dict], Field(description="List of ARC definitions in RO-Crate JSON format")]


class CreateOrUpdateArcsResponse(ApiResponse):
    """Response model for create or update ARC operations (Task Ticket or Result)."""

    rdi: Annotated[str | None, Field(description="Research Data Infrastructure identifier the ARCs belong to")] = None
    arcs: Annotated[list[ArcResponse], Field(description="List of ARC responses for the operation")] = Field(
        default_factory=list
    )

    # Async task fields
    task_id: Annotated[str | None, Field(description="The ID of the background task processing the ARC")] = None
    status: Annotated[str | None, Field(description="The status of the task submission")] = None


class GetTaskStatusResponse(BaseModel):
    """Response model for task status."""

    task_id: Annotated[str, Field(description="The ID of the background task")]
    status: Annotated[str, Field(description="The status of the task")]
    result: Annotated[
        CreateOrUpdateArcsResponse | None,
        Field(description="The result of the task if completed"),
    ] = None
    error: Annotated[str | None, Field(description="Error message if task failed")] = None
