from abc import ABC, abstractmethod
import logging
from typing import Optional
from arctrl import ARC


logger = logging.getLogger(__name__)


class ArcStoreError(Exception):
    """
    Excpetion base class for all ArcStore errors
    """
    pass


# ----------- Interface -----------

class ArcStore(ABC):

    @abstractmethod
    async def _create_or_update(self, arc_id: str, arc: ARC) -> None:
        """creates or updates an ARC"""
        raise NotImplementedError('`ArcStore._create_or_update` is not implemented')

    @abstractmethod
    def _get(self, arc_id: str) -> ARC:
        """returns an ARC of a given id"""
        raise NotImplementedError('`ArcStore._get` is not implemented')

    @abstractmethod
    def _delete(self, arc_id: str) -> None:
        """deletes an ARC of a given id"""
        raise NotImplementedError('`ArcStore._delete` is not implemented')
    
    @abstractmethod
    def _exists(self, arc_id: str) -> bool:
        """checks if an ARC of a given id already exists"""
        raise NotImplementedError('`ArcStore._exists` is not implemented')

    async def create_or_update(self, arc_id: str, arc: ARC) -> None:
        try:
            return await self._create_or_update(arc_id, arc)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(f"Caught exception when trying to create or update ARC '{arc_id}': {str(e)}")
            raise ArcStoreError(
                f"general exception caught in `ArcStore.create_or_update`: {str(e)}") from e
        
    def get(self, arc_id: str) -> Optional[ARC]:
        try:
            return self._get(arc_id)
        except Exception as e:
            logger.exception(f"Caught exception when trying to retrieve ARC '{arc_id}': {str(e)}")
            return None
        
    def delete(self, arc_id: str) -> None:
        try:
            return self._delete(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(f"Caught exception when trying to delete ARC '{arc_id}': {str(e)}")
            raise ArcStoreError(
                f"general exception caught in `ArcStore.delete`: {str(e)}") from e

    def exists(self, arc_id: str) -> bool:
        try:
            return self._exists(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            logger.exception(f"Caught exception when trying to check if ARC '{arc_id}' exists: {str(e)}")
            raise ArcStoreError(
                f"general exception caught in `ArcStore.delete`: {str(e)}") from e