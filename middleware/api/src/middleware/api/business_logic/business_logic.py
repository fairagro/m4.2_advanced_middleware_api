"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides the ``BusinessLogic`` façade that coordinates all domain services:

- :class:`ArcManager` — ARC creation, update, and GitLab synchronization
- :class:`HarvestManager` — harvest-run lifecycle management
- Health checks and infrastructure lifecycle

For the two-phase operation:
1. Fast CouchDB storage (used by API for immediate response)
2. Slow GitLab sync (executed by background worker)
"""

import logging
from types import TracebackType
from typing import Self

from middleware.api.arc_store import ArcStore
from middleware.api.document_store import DocumentStore
from middleware.api.document_store.arc_document import ArcMetadata
from middleware.api.document_store.harvest_document import HarvestDocument
from middleware.shared.api_models.common.models import ArcOperationResult, HarvestStatus
from middleware.shared.api_models.common.rocrate import RoCratePayload
from middleware.shared.json_types import RoCrateContent

from .arc_manager import ArcManager
from .config import BusinessLogicConfig
from .exceptions import (
    BusinessLogicError,
    InvalidJsonSemanticError,
    SetupError,
    TransientError,
)
from .harvest_manager import HarvestManager
from .ports import BusinessLogicPorts
from .task_payloads import CatalogFinalizeTask

logger = logging.getLogger(__name__)

__all__ = [
    "BusinessLogic",
    "BusinessLogicError",
    "InvalidJsonSemanticError",
    "SetupError",
    "TransientError",
]


class BusinessLogic:
    """Unified business logic for ARC processing.

    This class handles both fast CouchDB storage (for immediate API responses)
    and slow GitLab synchronization (for background workers).

    Architecture:
    - API calls create_or_update_arc() which stores in CouchDB and enqueues GitLab sync
    - Worker calls sync_to_gitlab() to perform the slow GitLab synchronization
    """

    def __init__(
        self,
        config: BusinessLogicConfig,
        store: ArcStore,
        doc_store: DocumentStore,
        ports: BusinessLogicPorts | None = None,
    ) -> None:
        """Initialize the BusinessLogic.

        Args:
            config: Middleware API configuration.
            store: ArcStore for GitLab persistence.
            doc_store: DocumentStore for CouchDB persistence.
            ports: Optional infrastructure adapters for API mode integrations.
        """
        resolved_ports = ports or BusinessLogicPorts()
        self._config = config
        self._doc_store = doc_store
        self._ports = resolved_ports
        self._broker_health_checker = resolved_ports.broker_health_checker
        self._harvest_manager = HarvestManager.from_config(config.harvest, doc_store)
        self._arc_manager = ArcManager(
            store=store,
            doc_store=doc_store,
            task_dispatcher=resolved_ports.task_dispatcher,
        )

    @property
    def harvest_manager(self) -> HarvestManager:
        """Harvest manager service."""
        return self._harvest_manager

    @property
    def config(self) -> BusinessLogicConfig:
        """Business-logic configuration."""
        return self._config

    @property
    def document_store(self) -> DocumentStore:
        """Underlying document store instance."""
        return self._doc_store

    @property
    def arc_store(self) -> ArcStore:
        """Underlying arc store instance (used by health checks)."""
        return self._arc_manager.store

    async def get_metadata(self, arc_id: str) -> ArcMetadata | None:
        """Get metadata for an ARC.

        Args:
            arc_id: The ID of the ARC.

        Returns:
            The ArcMetadata for the ARC, or None if not found.
        """
        return await self._doc_store.get_metadata(arc_id)

    async def health_check(self) -> dict[str, bool]:
        """Check health of stores and message broker."""
        couchdb_ok = await self._doc_store.health_check()

        rabbitmq_ok = False
        if self._broker_health_checker is not None:
            rabbitmq_ok = self._broker_health_checker.is_healthy()

        return {
            "couchdb_reachable": couchdb_ok,
            "rabbitmq": rabbitmq_ok,
        }

    async def startup(self) -> None:
        """Initialize business logic and its underlying stores.

        This ensures connections are established and required infrastructure
        (like database indices) is present.
        """
        try:
            await self._doc_store.connect()
            await self._doc_store.setup()
        except Exception as e:
            logger.error("Failed to setup business logic: %s", e, exc_info=True)
            raise SetupError(f"Failed to setup business logic: {e}") from e

    async def shutdown(self) -> None:
        """Close all background connections and perform cleanup."""
        await self._doc_store.close()
        await self._arc_manager.shutdown()

    async def __aenter__(self) -> Self:
        """Enter async context, ensuring setup is complete.

        This allows using BusinessLogic with an 'async with' block.
        """
        await self.startup()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit async context, ensuring shutdown is performed."""
        await self.shutdown()

    async def create_or_update_arc(
        self, rdi: str, arc: RoCratePayload | RoCrateContent, client_id: str | None, harvest_id: str | None = None
    ) -> ArcOperationResult:
        """Create or update an ARC with fast CouchDB storage and async GitLab sync.

        This method performs fast CouchDB storage and enqueues GitLab sync.
        It must only be called by the API (requires configured task_dispatcher).

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: ARC definition.
            client_id: The client identifier.
            harvest_id: Optional harvest run identifier.

        Returns:
            ArcOperationResult: Response containing details of the processed ARC.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation or if not in API mode.
        """
        # If harvest_id is provided, validate that it belongs to the client
        if harvest_id:
            await self._harvest_manager.validate_client_id(harvest_id, client_id)

        return await self._arc_manager.create_or_update_arc(rdi, arc, client_id, harvest_id)

    async def transition_harvest(
        self,
        harvest: HarvestDocument,
        target_status: HarvestStatus,
        client_id: str | None,
    ) -> HarvestDocument:
        """Transition a harvest and enqueue catalog finalize when appropriate."""
        updated = await self._harvest_manager.transition_harvest(harvest, target_status, client_id)
        if (
            target_status == HarvestStatus.COMPLETED
            and self._ports.task_dispatcher is not None
            and not self._arc_manager.store.publishes_per_arc_git
        ):
            stats = updated.statistics
            if stats.arcs_new + stats.arcs_updated > 0:
                self._ports.task_dispatcher.dispatch_finalize_catalog(
                    CatalogFinalizeTask(
                        rdi=updated.rdi,
                        harvest_id=updated.doc_id,
                        client_id=client_id,
                    )
                )
            else:
                logger.info(
                    "Skipping catalog finalize enqueue for harvest %s (no new or updated ARCs)",
                    updated.doc_id,
                )
        return updated

    async def complete_harvest(
        self,
        harvest: HarvestDocument,
        client_id: str | None,
    ) -> HarvestDocument:
        """Mark a harvest completed and enqueue catalog finalize when configured."""
        return await self.transition_harvest(harvest, HarvestStatus.COMPLETED, client_id)

    async def finalize_catalog(self, rdi: str, *, harvest_id: str | None = None) -> bool:
        """Publish consolidated catalog for an RDI (worker mode)."""
        return await self._arc_manager.finalize_catalog(rdi, harvest_id=harvest_id)

    async def sync_to_gitlab(self, rdi: str, arc: RoCratePayload | RoCrateContent) -> None:
        """Synchronize ARC to GitLab storage.

        This method performs the slow GitLab sync operation. It must only be
        called by background workers (requires NO task_dispatcher).

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: ARC definition.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation or if in API mode.
        """
        await self._arc_manager.sync_to_gitlab(rdi, arc)
