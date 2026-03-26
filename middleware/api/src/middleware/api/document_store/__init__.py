"""Contains the DocumentStore interface and its implementations."""

from abc import ABC, abstractmethod
from typing import Any

from .arc_document import ArcEvent, ArcMetadata
from .harvest_document import HarvestDocument, HarvestStatistics
from .task_record import TaskRecord


class DocumentStoreError(Exception):
    """Base exception for document store errors."""


class ArcStoreResult:
    """Result of storing an ARC."""

    def __init__(
        self,
        arc_id: str,
        is_new: bool,
        has_changes: bool,
    ):
        """Initialize an ArcStoreResult instance.

        Args:
            arc_id: The identifier of the ARC.
            is_new: Indicates if the ARC is new.
            has_changes: Indicates if the ARC has changes.
        """
        self.arc_id = arc_id
        self.is_new = is_new
        self.has_changes = has_changes


class DocumentStore(ABC):
    """Abstract base for document-based ARC storage."""

    @abstractmethod
    async def store_arc(
        self,
        rdi: str,
        arc_content: dict[str, Any],
        harvest_id: str | None = None,
        identifier: str | None = None,
    ) -> ArcStoreResult:
        """Store ARC with change detection.

        Args:
            rdi: Research Data Infrastructure identifier
            arc_content: RO-Crate JSON content
            harvest_id: Optional harvest run identifier
            identifier: Pre-extracted RO-Crate identifier to avoid re-parsing.
                        Extracted from arc_content when omitted.

        Returns:
            ArcStoreResult containing status and flags
        """
        raise NotImplementedError

    @abstractmethod
    async def get_arc_content(self, arc_id: str) -> dict[str, Any] | None:
        """Get raw ARC RO-Crate JSON.

        Args:
            arc_id: ARC identifier

        Returns:
            Dict containing the RO-Crate JSON or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    async def get_metadata(self, arc_id: str) -> ArcMetadata | None:
        """Get ARC metadata without full content.

        Args:
            arc_id: ARC identifier

        Returns:
            ArcMetadata object or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    async def add_event(self, arc_id: str, event: ArcEvent) -> None:
        """Append event to ARC event log.

        Args:
            arc_id: ARC identifier
            event: Event to append
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if document store is reachable.

        Returns:
            True if healthy, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    async def setup(self) -> None:
        """Initialize the document store and its dependencies."""
        raise NotImplementedError

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the document store."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close the connection to the document store."""
        raise NotImplementedError

    @abstractmethod
    async def create_harvest(
        self,
        rdi: str,
        client_id: str | None,
        expected_datasets: int | None = None,
    ) -> str:
        """Create a new harvest record.

        Args:
            rdi: Research Data Infrastructure identifier
            client_id: Client identifier
            expected_datasets: Optional number of datasets expected to be harvested.

        Returns:
            The harvest_id of the created harvest
        """
        raise NotImplementedError

    @abstractmethod
    async def get_harvest(self, harvest_id: str) -> HarvestDocument | None:
        """Get harvest document.

        Args:
            harvest_id: Harvest identifier

        Returns:
            The harvest document or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    async def update_harvest(self, harvest_id: str, updates: dict[str, Any]) -> HarvestDocument:
        """Update a harvest record.

        Args:
            harvest_id: Harvest identifier
            updates: Dictionary of fields to update
        """
        raise NotImplementedError

    @abstractmethod
    async def list_harvests(
        self,
        rdi: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[HarvestDocument]:
        """List harvest records.

        Args:
            rdi: Optional RDI to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return (None = backend default)

        Returns:
            List of harvest documents
        """
        raise NotImplementedError

    @abstractmethod
    async def get_harvest_statistics(self, harvest_id: str) -> HarvestStatistics:
        """Calculate statistics for a given harvest run.

        Args:
            harvest_id: The ID of the harvest run.

        Returns:
            The calculated harvest statistics.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_task_record(self, task_id: str) -> TaskRecord | None:
        """Get persisted task status record for a task id.

        Args:
            task_id: Task identifier

        Returns:
            Task record model or ``None`` if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def save_task_record(self, task_record: TaskRecord) -> None:
        """Create or update a persisted task status record.

        Args:
            task_record: Task record model to persist
        """
        raise NotImplementedError
