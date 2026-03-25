"""Domain payload models for background ARC synchronization tasks."""

from typing import Any

from pydantic import BaseModel


class ArcSyncTask(BaseModel):
    """Payload for ARC synchronization tasks."""

    rdi: str
    arc: dict[str, Any]
    client_id: str | None = None
