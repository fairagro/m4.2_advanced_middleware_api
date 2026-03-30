"""Legacy task status types used by v1/v2 task polling endpoints."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SyncTaskStatus(StrEnum):
    """Status of a legacy async task exposed by v1/v2 endpoints."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


@dataclass
class SyncTaskResult:
    """Legacy task status query result used by v1/v2 endpoints."""

    status: SyncTaskStatus
    result: dict[str, Any] | None = field(default=None)
    error: str | None = field(default=None)
