"""Domain payload models for background ARC synchronization tasks."""

from pydantic import BaseModel

from middleware.shared.json_types import RoCrateContent


class ArcSyncTask(BaseModel):
    """Payload for ARC synchronization tasks."""

    rdi: str
    arc: RoCrateContent
    client_id: str | None = None


class CatalogFinalizeTask(BaseModel):
    """Payload for consolidated catalog finalize tasks."""

    rdi: str
    harvest_id: str | None = None
    client_id: str | None = None
