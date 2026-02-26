"""Harvest manager service for handling harvest-run lifecycles."""

import logging
from typing import Any, Self

from middleware.api.config import HarvestConfig
from middleware.api.document_store import DocumentStore
from middleware.api.document_store.harvest_document import HarvestDocument
from middleware.shared.api_models.common.models import HarvestStatus

logger = logging.getLogger(__name__)


class HarvestManager:
    """Service for managing harvest runs."""

    def __init__(self, doc_store: DocumentStore, config: HarvestConfig):
        """Initialize with DocumentStore and configuration."""
        self._doc_store = doc_store
        self._config = config

    @classmethod
    def from_config(cls, config: HarvestConfig, doc_store: DocumentStore) -> Self:
        """Create a HarvestManager from configuration and DocumentStore.

        This factory method encapsulates the initialization logic, making it easy
        to test and reuse.

        Args:
            config: HarvestConfig with harvest run settings.
            doc_store: DocumentStore for persistence.

        Returns:
            HarvestManager: Initialized manager instance.
        """
        return cls(doc_store, config)

    async def create_harvest(self, rdi: str, client_id: str, expected_datasets: int | None = None) -> str:
        """Start a new harvest run."""
        harvest_id = await self._doc_store.create_harvest(rdi, client_id, expected_datasets=expected_datasets)
        logger.info("[%s] Created harvest: %s (rdi=%s)", client_id, harvest_id, rdi)
        return harvest_id

    async def get_harvest(self, harvest_id: str) -> HarvestDocument | None:
        """Get harvest details."""
        return await self._doc_store.get_harvest(harvest_id)

    async def validate_client_id(self, harvest_id: str, client_id: str) -> None:
        """Validate that the harvest belongs to the client."""
        harvest = await self.get_harvest(harvest_id)
        if not harvest:
            raise ValueError(f"Harvest {harvest_id} not found")

        # The field in CouchDB is 'client_id'
        stored_client_id = harvest.client_id
        if stored_client_id != client_id:
            logger.warning(
                "[%s] Client ID mismatch for harvest %s: expected %s", client_id, harvest_id, stored_client_id
            )
            raise ValueError(f"Harvest {harvest_id} does not belong to client {client_id}")

    async def complete_harvest(self, harvest_id: str, client_id: str) -> HarvestDocument:
        """Mark a harvest as completed and return the updated document."""
        # Single fetch: used for both client_id validation and expected_datasets
        harvest = await self.get_harvest(harvest_id)
        if not harvest:
            raise ValueError(f"Harvest {harvest_id} not found")
        if harvest.client_id != client_id:
            logger.warning(
                "[%s] Client ID mismatch for harvest %s: expected %s", client_id, harvest_id, harvest.client_id
            )
            raise ValueError(f"Harvest {harvest_id} does not belong to client {client_id}")

        # Calculate statistics server-side from stored ARCs
        statistics = await self._doc_store.get_harvest_statistics(harvest_id)

        # Preserve expected_datasets if already set
        if harvest.statistics and harvest.statistics.expected_datasets is not None:
            statistics.expected_datasets = harvest.statistics.expected_datasets

        updates: dict[str, Any] = {
            "status": HarvestStatus.COMPLETED,
            "statistics": statistics.model_dump(),
        }

        updated = await self._doc_store.update_harvest(harvest_id, updates)
        logger.info("[%s] Completed harvest: %s", client_id, harvest_id)
        return updated

    async def cancel_harvest(self, harvest_id: str, client_id: str) -> None:
        """Cancel a harvest run."""
        # Single fetch: used for both client_id validation and RDI auth (endpoint does it first)
        harvest = await self.get_harvest(harvest_id)
        if not harvest:
            raise ValueError(f"Harvest {harvest_id} not found")
        if harvest.client_id != client_id:
            logger.warning(
                "[%s] Client ID mismatch for harvest %s: expected %s", client_id, harvest_id, harvest.client_id
            )
            raise ValueError(f"Harvest {harvest_id} does not belong to client {client_id}")

        updates = {
            "status": HarvestStatus.CANCELLED,
        }
        await self._doc_store.update_harvest(harvest_id, updates)
        logger.info("[%s] Cancelled harvest: %s", client_id, harvest_id)

    async def list_harvests(self, rdi: str | None = None) -> list[HarvestDocument]:
        """List harvest runs."""
        return await self._doc_store.list_harvests(rdi)
