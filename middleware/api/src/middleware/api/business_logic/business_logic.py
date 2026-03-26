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
from typing import Any, Self

from middleware.api.arc_store import ArcStore
from middleware.api.document_store import DocumentStore
from middleware.api.document_store.arc_document import ArcMetadata
from middleware.shared.api_models.common.models import ArcOperationResult

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
        self._broker_health_checker = resolved_ports.broker_health_checker
        self._harvest_manager = HarvestManager.from_config(config.harvest, doc_store)
        self._arc_manager = ArcManager(
            store=store,
            doc_store=doc_store,
            task_dispatcher=resolved_ports.task_dispatcher,
        )

    @property
    def harvest_manager(self) -> HarvestManager:
        """Get the harvest manager service."""
        return self._harvest_manager

    @property
    def config(self) -> BusinessLogicConfig:
        """Get the configuration."""
        return self._config

    @property
    def document_store(self) -> DocumentStore:
        """Get the underlying document store instance."""
        return self._doc_store

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
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        """Exit async context, ensuring shutdown is performed."""
        await self.shutdown()

    async def create_or_update_arc(
        self, rdi: str, arc: dict[str, Any], client_id: str | None, harvest_id: str | None = None
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

    async def sync_to_gitlab(self, rdi: str, arc: dict[str, Any]) -> None:
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
