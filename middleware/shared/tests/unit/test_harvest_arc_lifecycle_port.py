"""Unit tests for HarvestArcLifecyclePort structural typing."""

from __future__ import annotations

from middleware.shared.api_models.common.models import ArcLifecycleStatus, ArcStatus, HarvestStatus
from middleware.shared.api_models.v3.models import (
    ArcMetadata,
    ArcResponse,
    CreateArcRequest,
    CreateHarvestRequest,
    HarvestResponse,
    LivenessResponse,
    PatchHarvestRequest,
    StatusResponse,
    SubmitHarvestArcRequest,
)
from middleware.shared.v3_lifecycle import CreateHarvestOutcome, HarvestArcLifecyclePort


class _StubPort:
    """Minimal stub that satisfies HarvestArcLifecyclePort."""

    async def create_harvest(
        self,
        body: CreateHarvestRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateHarvestOutcome:
        _ = idempotency_key
        return CreateHarvestOutcome(
            harvest=HarvestResponse(
                harvest_id="h1",
                rdi=body.rdi,
                status=HarvestStatus.RUNNING,
                started_at="2020-01-01T00:00:00Z",
                statistics={},
            )
        )

    async def get_harvest(self, harvest_id: str) -> HarvestResponse:
        return HarvestResponse(
            harvest_id=harvest_id,
            rdi="rdi",
            status=HarvestStatus.RUNNING,
            started_at="2020-01-01T00:00:00Z",
            statistics={},
        )

    async def patch_harvest(self, harvest_id: str, body: PatchHarvestRequest) -> HarvestResponse:
        return HarvestResponse(
            harvest_id=harvest_id,
            rdi="rdi",
            status=body.status,
            started_at="2020-01-01T00:00:00Z",
            completed_at="2020-01-01T00:00:01Z",
            statistics={},
        )

    async def complete_harvest(self, harvest_id: str) -> HarvestResponse:
        return HarvestResponse(
            harvest_id=harvest_id,
            rdi="rdi",
            status=HarvestStatus.COMPLETED,
            started_at="2020-01-01T00:00:00Z",
            completed_at="2020-01-01T00:00:01Z",
            statistics={},
        )

    async def submit_arc_in_harvest(self, harvest_id: str, body: SubmitHarvestArcRequest) -> ArcResponse:
        _ = harvest_id, body
        return _arc_response()

    async def create_or_update_arc(self, body: CreateArcRequest) -> ArcResponse:
        _ = body
        return _arc_response()

    async def liveness(self) -> LivenessResponse:
        return LivenessResponse(status=StatusResponse.OK, services={"api": True})


def _arc_response() -> ArcResponse:
    return ArcResponse(
        arc_id="abc",
        status=ArcStatus.CREATED,
        metadata=ArcMetadata(
            arc_hash="hash",
            status=ArcLifecycleStatus.ACTIVE,
            first_seen="2020-01-01T00:00:00Z",
            last_seen="2020-01-01T00:00:00Z",
        ),
    )


def test_stub_satisfies_harvest_arc_lifecycle_port() -> None:
    """A minimal stub is recognized as HarvestArcLifecyclePort at runtime."""
    stub: HarvestArcLifecyclePort = _StubPort()
    assert isinstance(stub, HarvestArcLifecyclePort)
