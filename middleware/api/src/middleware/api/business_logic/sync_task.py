"""Domain types for ARC GitLab sync task status queries."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SyncTaskStatus(StrEnum):
    """Status of an ARC GitLab sync task.

    Represents the domain-specific lifecycle states of an ARC during
    persistence into the ArcStore (GitLab), independent of Celery internals.
    """

    PENDING = "PENDING"
    """Task is queued and waiting to be processed."""

    RUNNING = "RUNNING"
    """Task is currently being executed by a worker."""

    SUCCESS = "SUCCESS"
    """Task completed successfully; ARC has been persisted in the ArcStore."""

    FAILURE = "FAILURE"
    """Task failed permanently; ARC was not persisted."""


@dataclass
class SyncTaskResult:
    """Domain representation of an ARC sync task query result.

    Returned by BusinessLogic.get_task_status to decouple callers from
    Celery internals.
    """

    status: SyncTaskStatus
    result: dict[str, Any] | None = field(default=None)
    error: str | None = field(default=None)
