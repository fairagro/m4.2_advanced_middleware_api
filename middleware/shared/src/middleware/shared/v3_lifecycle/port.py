"""Protocol for harvest/ARC lifecycle ops used by shared v3 HTTP routers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from middleware.shared.api_models.v3.models import (
    ArcResponse,
    CreateArcRequest,
    CreateHarvestRequest,
    HarvestResponse,
    LivenessResponse,
    PatchHarvestRequest,
    SubmitHarvestArcRequest,
)


@dataclass(frozen=True, slots=True)
class CreateHarvestOutcome:
    """Result of creating (or idempotently replaying) a harvest."""

    harvest: HarvestResponse
    replayed: bool = False


@runtime_checkable
class HarvestArcLifecyclePort(Protocol):
    """Backend operations for the ApiClient harvest/ARC lifecycle HTTP surface.

    Adapters own soft vs strict HTTP semantics (status codes / conflict mapping).
    Implementations may raise framework HTTP errors; this Protocol stays FastAPI-free.
    """

    async def create_harvest(
        self,
        body: CreateHarvestRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateHarvestOutcome:
        """Create a harvest run (or return the idempotent replay)."""
        ...

    async def get_harvest(self, harvest_id: str) -> HarvestResponse:
        """Return harvest details; adapter maps missing/unauthorized to HTTP errors."""
        ...

    async def patch_harvest(self, harvest_id: str, body: PatchHarvestRequest) -> HarvestResponse:
        """Transition a harvest to a terminal client status."""
        ...

    async def complete_harvest(self, harvest_id: str) -> HarvestResponse:
        """Complete a harvest (deprecated POST complete path)."""
        ...

    async def submit_arc_in_harvest(self, harvest_id: str, body: SubmitHarvestArcRequest) -> ArcResponse:
        """Submit an ARC within a harvest context."""
        ...

    async def create_or_update_arc(self, body: CreateArcRequest) -> ArcResponse:
        """Standalone ARC create/update."""
        ...

    async def liveness(self) -> LivenessResponse:
        """Successful process liveness probe."""
        ...
