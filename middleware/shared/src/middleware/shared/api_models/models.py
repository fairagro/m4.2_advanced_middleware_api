"""FAIRagro Middleware API Models package."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class ArcStatus(StrEnum):
    """Enumeration of possible ARC status values."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REQUESTED = "requested"


class TaskStatus(StrEnum):
    """Enumeration of possible task states.

    Values match Celery task states.
    """

    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


class LivenessResponse(BaseModel):
    """Response model for liveness check."""

    message: Annotated[str, Field(description="Liveness message")] = "ok"


class HealthResponse(BaseModel):
    """Response model for health check including backend status."""

    status: Annotated[str, Field(description="Overall service status (ok/error)")] = "ok"
    redis_reachable: Annotated[bool, Field(description="True if Redis is reachable")]
    rabbitmq_reachable: Annotated[bool, Field(description="True if RabbitMQ is reachable")]


class HealthResponseV2(BaseModel):
    """Response model for health check v2."""

    status: Annotated[str, Field(description="Overall service status (ok/error)")] = "ok"
    services: Annotated[dict[str, bool], Field(description="Dictionary of service statuses")]


class CreateOrUpdateArcsRequest(BaseModel):
    """Request model for creating or updating ARCs."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arcs: Annotated[list[dict], Field(description="List of ARC definitions in RO-Crate JSON format")]


class CreateOrUpdateArcRequest(BaseModel):
    """Request model for creating or updating a single ARC (v2)."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arc: Annotated[dict, Field(description="ARC definition in RO-Crate JSON format")]


class ApiResponse(BaseModel):
    """Base response model for business logic operations.

    Args:
        BaseModel (_type_): Pydantic BaseModel for data validation and serialization.

    """

    client_id: Annotated[
        str | None,
        Field(
            description="Client identifier which is the CN from the client certificate, "
            "or 'unknown' if client certificates are not required",
        ),
    ] = None
    message: Annotated[str, Field(description="Response message")] = ""


class WhoamiResponse(ApiResponse):
    """Response model for whoami operation."""

    accessible_rdis: Annotated[
        list[str], Field(description="List of Research Data Infrastructures the client is authorized for")
    ]


class ArcResponse(BaseModel):
    """Response model for individual ARC operations.

    Args:
        BaseModel (_type_): Pydantic BaseModel for data validation and serialization.

    """

    id: Annotated[str, Field(description="ARC identifier, as hashed value of the original identifier and RDI")]
    status: Annotated[ArcStatus, Field(description="Status of the ARC operation")]
    timestamp: Annotated[str, Field(description="Timestamp of the ARC operation in ISO 8601 format")]


class CreateOrUpdateArcsResponse(ApiResponse):
    """Response model for create or update ARC operations (Task Ticket or Result)."""

    rdi: Annotated[str | None, Field(description="Research Data Infrastructure identifier the ARCs belong to")] = None
    arcs: Annotated[list[ArcResponse], Field(description="List of ARC responses for the operation")] = Field(
        default_factory=list
    )

    # Async task fields
    task_id: Annotated[str | None, Field(description="The ID of the background task processing the ARC")] = None
    status: Annotated[str | None, Field(description="The status of the task submission")] = None


class CreateOrUpdateArcResponse(ApiResponse):
    """Response model for create or update a single ARC operation ticket (v2)."""

    task_id: Annotated[str, Field(description="The ID of the background task")]
    status: Annotated[TaskStatus, Field(description="The status of the task")]


class ArcOperationResult(ApiResponse):
    """Response model for the actual result of a single ARC operation (v2)."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier the ARC belongs to")]
    arc: Annotated[ArcResponse, Field(description="ARC response for the operation")]


class ArcTaskTicket(ApiResponse):
    """Response model for a newly created async task ticket."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier the ARC belongs to")]
    task_id: Annotated[str, Field(description="Async task ID")]


class GetTaskStatusResponse(BaseModel):
    """Response model for task status (v1)."""

    task_id: Annotated[str, Field(description="The ID of the background task")]
    status: Annotated[str, Field(description="The status of the task")]
    result: Annotated[
        CreateOrUpdateArcsResponse | None,
        Field(description="The result of the task if completed"),
    ] = None
    error: Annotated[str | None, Field(description="Error message if task failed")] = None


class GetTaskStatusResponseV2(ApiResponse):
    """Response model for task status (v2)."""

    status: Annotated[TaskStatus, Field(description="The status of the task")]
    result: Annotated[
        ArcOperationResult | None,
        Field(description="The result of the task if completed"),
    ] = None
