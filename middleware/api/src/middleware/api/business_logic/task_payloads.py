"""Domain payload models for background ARC synchronization tasks."""

from pydantic import BaseModel


class ArcSyncTask(BaseModel):
    """Payload for ARC synchronization tasks."""

    rdi: str
    arc: str
    client_id: str | None = None
    # Defaults True keep old queue messages safe (always full sync until API+worker roll out).
    is_new: bool = True
    has_changes: bool = True


class CatalogFinalizeTask(BaseModel):
    """Payload for consolidated catalog finalize tasks."""

    rdi: str
    harvest_id: str | None = None
    client_id: str | None = None
