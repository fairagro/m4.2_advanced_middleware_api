"""FAIRagro Middleware API Models package."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class ArcStatus(str, Enum):
    """Enumeration of possible ARC status values.

    Values:
        created: ARC was newly created
        updated: ARC was updated
        deleted: ARC was deleted
        requested: ARC was requested

    """

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REQUESTED = "requested"


class LivenessResponse(BaseModel):
    """Response model for liveness check."""

    message: Annotated[str, Field(description="Liveness message")] = "ok"


class CreateOrUpdateArcsRequest(BaseModel):
    """Request model for creating or updating ARCs."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    arcs: Annotated[list[dict], Field(description="List of ARC definitions in RO-Crate JSON format")]


class ApiResponse(BaseModel):
    """Base response model for business logic operations.

    Args:
        BaseModel (_type_): Pydantic BaseModel for data validation and serialization.

    """

    client_id: Annotated[
        str | None,
        Field(
            description="Client identifier which is the CN from the client certificate, "
            "or None if client certificates are not required"
        ),
    ]
    message: Annotated[str, Field(description="Response message")]


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
    """Response model for create or update ARC operations."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier the ARCs belong to")]
    arcs: Annotated[list[ArcResponse], Field(description="List of ARC responses for the operation")]
