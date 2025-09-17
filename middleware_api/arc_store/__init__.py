"""Contains the ArcStore interface and its implementations."""

import logging
from abc import ABC, abstractmethod

from arctrl import ARC

logger = logging.getLogger(__name__)


class ArcStoreError(Exception):
    """Excpetion base class for all ArcStore errors."""


# ----------- Interface -----------


class ArcStore(ABC):
    """Abstract base class for ARC storage backends."""

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
        try:
            return await self._create_or_update(arc_id, arc)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(
                "Caught exception when trying to create or update ARC '%s': %s",
                arc_id,
                str(e),
            )
            raise ArcStoreError(
                f"General exception caught in `ArcStore.create_or_update`: {str(e)}"
            ) from e

    def get(self, arc_id: str) -> ARC | None:
        """_Get an ARC by its ID.

        Args:
            arc_id (str): ID of the ARC to retrieve.

        Returns:
            Optional[ARC]: The ARC object if found, otherwise None.

        """
        try:
            return self._get(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(
                "Caught exception when trying to retrieve ARC '%s': %s", arc_id, str(e)
            )
            raise

    def delete(self, arc_id: str) -> None:
        """_Delete an ARC by its ID.

        Args:
            arc_id (str): ID of the ARC to delete.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            _type_: None

        """
        try:
            return self._delete(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(
                "Caught exception when trying to delete ARC '%s': %s", arc_id, str(e)
            )
            raise ArcStoreError(
                f"general exception caught in `ArcStore.delete`: '{str(e)}'"
            ) from e

    def exists(self, arc_id: str) -> bool:
        """_Check if an ARC exists by its ID.

        Args:
            arc_id (str): ID of the ARC to check.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            bool: True if the ARC exists, False otherwise.

        """
        try:
            return self._exists(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(
                "Caught exception when trying to check if ARC '%s' exists: %s",
                arc_id,
                str(e),
            )
            raise ArcStoreError(
                f"General exception caught in `ArcStore.delete`: {str(e)}"
            ) from e
