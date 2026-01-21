"""Contains the ArcStore interface and its implementations."""

import hashlib
import logging
from abc import ABC, abstractmethod

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

logger = logging.getLogger(__name__)


class ArcStoreError(Exception):
    """Excpetion base class for all ArcStore errors."""


# ----------- Interface -----------


class ArcStore(ABC):
    """Abstract base class for ARC storage backends."""

    def __init__(self) -> None:
        """Initialize ArcStore with tracer."""
        self._tracer = trace.get_tracer(__name__)

    def arc_id(self, identifier: str, rdi: str) -> str:
        """Generate ARC ID."""
        input_str = f"{identifier}:{rdi}"
        return hashlib.sha256(input_str.encode("utf-8")).hexdigest()

    @abstractmethod
    async def _create_or_update(self, arc_id: str, arc: ARC) -> None:
        """Create or updates an ARC."""
        raise NotImplementedError("`ArcStore._create_or_update` is not implemented")

    @abstractmethod
    def _get(self, arc_id: str) -> ARC:
        """Return an ARC of a given id."""
        raise NotImplementedError("`ArcStore._get` is not implemented")

    @abstractmethod
    def _delete(self, arc_id: str) -> None:
        """Delete an ARC of a given id."""
        raise NotImplementedError("`ArcStore._delete` is not implemented")

    @abstractmethod
    def _exists(self, arc_id: str) -> bool:
        """Check if an ARC of a given id already exists."""
        raise NotImplementedError("`ArcStore._exists` is not implemented")

    @abstractmethod
    def _check_health(self) -> bool:
        """Check connection to the storage backend."""
        raise NotImplementedError("`ArcStore._check_health` is not implemented")

    async def create_or_update(self, arc_id: str, arc: ARC) -> None:
        """_Create or update an ARC.

        Args:
            arc_id (str): ID of the ARC to create or update.
            arc (ARC): ARC object to create or update.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            _type_: None

        """
        with self._tracer.start_as_current_span(
            "arc_store.create_or_update",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                return await self._create_or_update(arc_id, arc)
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception(
                    "Caught exception when trying to create or update ARC '%s': %s",
                    arc_id,
                    str(e),
                )
                span.record_exception(e)
                raise ArcStoreError(f"General exception caught in `ArcStore.create_or_update`: {str(e)}") from e

    def get(self, arc_id: str) -> ARC | None:
        """_Get an ARC by its ID.

        Args:
            arc_id (str): ID of the ARC to retrieve.

        Returns:
            Optional[ARC]: The ARC object if found, otherwise None.

        """
        with self._tracer.start_as_current_span(
            "arc_store.get",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                arc = self._get(arc_id)
                span.set_attribute("found", arc is not None)
                return arc
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception("Caught exception when trying to retrieve ARC '%s'", arc_id)
                span.record_exception(e)
                raise ArcStoreError(f"General exception caught in `ArcStore.get`: {e!r}") from e

    def delete(self, arc_id: str) -> None:
        """_Delete an ARC by its ID.

        Args:
            arc_id (str): ID of the ARC to delete.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            _type_: None

        """
        with self._tracer.start_as_current_span(
            "arc_store.delete",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                return self._delete(arc_id)
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception("Caught exception when trying to delete ARC '%s': %s", arc_id, str(e))
                span.record_exception(e)
                raise ArcStoreError(f"general exception caught in `ArcStore.delete`: '{str(e)}'") from e

    def exists(self, arc_id: str) -> bool:
        """_Check if an ARC exists by its ID.

        Args:
            arc_id (str): ID of the ARC to check.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            bool: True if the ARC exists, False otherwise.

        """
        with self._tracer.start_as_current_span(
            "arc_store.exists",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                exists = self._exists(arc_id)
                span.set_attribute("exists", exists)
                return exists
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                msg = f"Caught exception when trying to check if ARC '{arc_id}' exists: {e!r}"
                logger.exception(msg)
                span.record_exception(e)
                raise ArcStoreError(msg) from e

    def check_health(self) -> bool:
        """Check connection to the storage backend.

        Returns:
            bool: True if backend is reachable, False otherwise.
        """
        try:
            return self._check_health()
        except (RuntimeError, OSError, ValueError, ConnectionError, TimeoutError) as e:
            logger.exception("Caught exception during health check: %s", str(e))
            return False
