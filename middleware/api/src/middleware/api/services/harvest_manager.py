"""Harvest manager service for handling harvest-run lifecycles."""

import logging
from typing import Any

from middleware.api.document_store import DocumentStore
from middleware.api.schemas import HarvestStatus

logger = logging.getLogger(__name__)


class HarvestManager:
    """Service for managing harvest runs."""

    def __init__(self, doc_store: DocumentStore):
        """Initialize with DocumentStore."""
        self._doc_store = doc_store

    async def create_harvest(self, rdi: str, source: str, config: dict | None = None) -> str:
        """Start a new harvest run."""
        harvest_id = await self._doc_store.create_harvest(rdi, source, config)
        logger.info("Created harvest: %s (rdi=%s, source=%s)", harvest_id, rdi, source)
        return harvest_id

    async def get_harvest(self, harvest_id: str) -> dict[str, Any] | None:
        """Get harvest details."""
        return await self._doc_store.get_harvest(harvest_id)

    async def complete_harvest(self, harvest_id: str, statistics: dict | None = None) -> None:
        """Mark a harvest as completed."""
        updates = {
            "status": HarvestStatus.COMPLETED,
        }
        if statistics:
            # Note: In a full implementation, we might want to merge or validate statistics
            updates["statistics"] = statistics
            
        await self._doc_store.update_harvest(harvest_id, updates)
        logger.info("Completed harvest: %s", harvest_id)

    async def cancel_harvest(self, harvest_id: str) -> None:
        """Cancel a harvest run."""
        updates = {
            "status": HarvestStatus.CANCELLED,
        }
        await self._doc_store.update_harvest(harvest_id, updates)
        logger.info("Cancelled harvest: %s", harvest_id)

    async def list_harvests(self, rdi: str | None = None) -> list[dict[str, Any]]:
        """List harvest runs."""
        return await self._doc_store.list_harvests(rdi)
