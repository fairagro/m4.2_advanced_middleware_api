"""V1 API Models."""

from typing import Annotated

from pydantic import BaseModel, Field

from ..common.models import ApiResponse


class LivenessResponse(BaseModel):
    """Response model for liveness check."""

    message: Annotated[str, Field(description="Liveness message")] = "ok"


class HealthResponse(BaseModel):
    """Response model for health check including backend status."""

    status: Annotated[str, Field(description="Overall service status (ok/error)")] = "ok"
    rabbitmq_reachable: Annotated[bool, Field(description="True if RabbitMQ is reachable")]


class WhoamiResponse(ApiResponse):
    """Response model for whoami operation."""

    accessible_rdis: Annotated[
        list[str], Field(description="List of Research Data Infrastructures the client is authorized for")
    ]
