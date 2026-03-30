"""Task status record model for legacy v1/v2 task endpoints."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class TaskArcStatus(StrEnum):
    """Persisted ARC operation status values for task records."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REQUESTED = "requested"


class TaskRecordStatus(StrEnum):
    """Persisted task lifecycle status values for legacy task polling."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class TaskArcResponse(BaseModel):
    """Minimal ARC payload persisted in task records."""

    id: str
    status: TaskArcStatus
    timestamp: datetime


class TaskArcOperationResult(BaseModel):
    """Minimal operation result persisted for legacy task polling."""

    client_id: Annotated[str | None, Field(default=None)] = None
    message: Annotated[str, Field(default="")]
    rdi: str
    arc: TaskArcResponse


class TaskRecord(BaseModel):
    """Persisted task status record in document storage."""

    task_id: str
    status: TaskRecordStatus
    result: TaskArcOperationResult | None = None
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
