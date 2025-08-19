from abc import ABC, abstractmethod
from typing import Optional
from arctrl.arc import ARC

# ----------- Interface -----------

class ARCPersistence(ABC):
    @abstractmethod
    def create_or_update(self, arc_id: str, arc: ARC) -> None:
        """Erstellt oder aktualisiert ein ARC"""
        pass

    @abstractmethod
    def get(self, arc_id: str) -> Optional[ARC]:
        """Liest ein ARC anhand seiner ID"""
        pass

    @abstractmethod
    def delete(self, arc_id: str) -> None:
        """Löscht ein ARC anhand seiner ID"""
        pass