"""Contains the DocumentStore interface and its implementations."""

from abc import ABC, abstractmethod
from typing import Any

from middleware.api.schemas import ArcEvent, ArcMetadata


class DocumentStoreError(Exception):
    """Base exception for document store errors."""


class ArcStoreResult:
    """Result of storing an ARC."""

    def __init__(
        self,
        arc_id: str,
        is_new: bool,
        has_changes: bool,
        should_trigger_git: bool,
    ):
        """Initialize an ArcStoreResult instance.

        Args:
            arc_id: The identifier of the ARC.
            is_new: Indicates if the ARC is new.
            has_changes: Indicates if the ARC has changes.
            should_trigger_git: Indicates if the ARC should trigger a Git operation.
        """
        self.arc_id = arc_id
        self.is_new = is_new
        self.has_changes = has_changes
        self.should_trigger_git = should_trigger_git


class DocumentStore(ABC):
    """Abstract base for document-based ARC storage."""

    @abstractmethod
    async def store_arc(
        self,
        rdi: str,
        arc_content: dict[str, Any],
        harvest_id: str | None = None,
    ) -> ArcStoreResult:
        """Store ARC with change detection.

        Args:
            rdi: Research Data Infrastructure identifier
            arc_content: RO-Crate JSON content
            harvest_id: Optional harvest run identifier

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
    async def setup(self, setup_system: bool = False) -> None:
        """Initialize the document store and its dependencies.

        Args:
            setup_system: Whether to ensure system databases exist.
        """
        raise NotImplementedError

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the document store."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close the connection to the document store."""
        raise NotImplementedError
