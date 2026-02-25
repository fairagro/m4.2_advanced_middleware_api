"""Common models and enums shared across API versions."""

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


class ArcLifecycleStatus(StrEnum):
    """ARC lifecycle status in the system."""

    ACTIVE = "ACTIVE"  # Normal active state
    PROCESSING = "PROCESSING"  # Git workflow in progress
    MISSING = "MISSING"  # Not seen in recent harvest
    DELETED = "DELETED"  # Soft-deleted (not physically removed)
    INVALID = "INVALID"  # Validation failed


class ArcEventType(StrEnum):
    """Types of events in the ARC event log."""

    # Lifecycle events
    ARC_CREATED = "ARC_CREATED"
    ARC_UPDATED = "ARC_UPDATED"
    ARC_NOT_SEEN = "ARC_NOT_SEEN"
    ARC_MARKED_MISSING = "ARC_MARKED_MISSING"
    ARC_MARKED_DELETED = "ARC_MARKED_DELETED"
    ARC_RESTORED = "ARC_RESTORED"  # Reappeared after being marked missing/deleted
    ARC_NOT_CHANGED = "ARC_NOT_CHANGED"  # Explicitly tracking no-change events (if needed)

    # Git workflow events
    GIT_QUEUED = "GIT_QUEUED"
    GIT_PROCESSING = "GIT_PROCESSING"
    GIT_PUSH_SUCCESS = "GIT_PUSH_SUCCESS"
    GIT_PUSH_FAILED = "GIT_PUSH_FAILED"

    # Validation events
    VALIDATION_WARNING = "VALIDATION_WARNING"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_SUCCESS = "VALIDATION_SUCCESS"

    # Operator actions
    OPERATOR_NOTE = "OPERATOR_NOTE"
    MANUAL_DELETION = "MANUAL_DELETION"


class HarvestStatus(StrEnum):
    """Harvest run status."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


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
