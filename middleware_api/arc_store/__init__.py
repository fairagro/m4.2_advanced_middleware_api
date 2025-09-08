from abc import ABC, abstractmethod
from typing import Optional
from arctrl import ARC


class ArcStoreError(Exception):
    """
    Excpetion base class for all ArcStore errors
    """
    pass


# ----------- Interface -----------

class ArcStore(ABC):

    @abstractmethod
    def _create_or_update(self, arc_id: str, arc: ARC) -> None:
        """creates or updates an ARC"""
        raise NotImplementedError('`ArcStore._create_or_update` is not implemented')

    @abstractmethod
    def _get(self, arc_id: str) -> Optional[ARC]:
        """returns an ARC of a given id"""
        raise NotImplementedError('`ArcStore._get` is not implemented')

    @abstractmethod
    def _delete(self, arc_id: str) -> None:
        """deletes an ARC of a given id"""
        raise NotImplementedError('`ArcStore._delete` is not implemented')
    
    def create_or_update(self, arc_id: str, arc: ARC) -> None:
        try:
            return self._create_or_update(arc_id, arc)
        except ArcStoreError:
            raise
        except Exception as e:
            raise ArcStoreError(
                f"generall exception caught in `ArcStore.create_or_update`: {str(e)}") from e
        
    def get(self, arc_id: str) -> Optional[ARC]:
        try:
            return self._get(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            raise ArcStoreError(
                f"generall exception caught in `ArcStore._get`: {str(e)}") from e
        
    def delete(self, arc_id: str) -> None:
        try:
            return self._delete(arc_id)
        except ArcStoreError:
            raise
        except Exception as e:
            raise ArcStoreError(
                f"generall exception caught in `ArcStore.delete`: {str(e)}") from e