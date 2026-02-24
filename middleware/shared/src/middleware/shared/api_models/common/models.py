"""Common models and enums shared across API versions."""

from enum import StrEnum
from typing import Annotated, Any

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


class ApiResponse(BaseModel):
    """Base response model for business logic operations."""

    client_id: Annotated[
        str | None,
        Field(
            description="Client identifier which is the CN from the client certificate, "
            "or 'unknown' if client certificates are not required",
        ),
    ] = None
    message: Annotated[str, Field(description="Response message")] = ""


class ArcResponse(BaseModel):
    """Response model for individual ARC operations."""

    id: Annotated[str, Field(description="ARC identifier, as hashed value of the original identifier and RDI")]
    status: Annotated[ArcStatus, Field(description="Status of the ARC operation")]
    timestamp: Annotated[str, Field(description="Timestamp of the ARC operation in ISO 8601 format")]


class ArcOperationResult(ApiResponse):
    """Response model for the actual result of a single ARC operation."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier the ARC belongs to")]
    arc: Annotated[ArcResponse, Field(description="ARC response for the operation")]


class ArcSyncTask(BaseModel):
    """Payload for ARC synchronization tasks."""

    rdi: str
    arc: dict[str, Any]
