"""Unit tests for shared api_v3 mount helper and route table."""

from __future__ import annotations

from fastapi import FastAPI, Request

from middleware.api_v3 import MVP_LIFECYCLE_ROUTES, mount_lifecycle_routes
from middleware.api_v3.mount import (
    assert_mvp_lifecycle_routes,
    collect_route_methods,
    collect_route_response_models,
)
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


def _stub_factory(_request: Request) -> HarvestArcLifecyclePort:
    return _StubPort()


def test_mount_exposes_mvp_lifecycle_paths_and_methods() -> None:
    """A tiny FastAPI app with a stub port exposes the MVP lifecycle surface."""
    app = FastAPI()
    mount_lifecycle_routes(app, _stub_factory)
    assert_mvp_lifecycle_routes(app)

    present = collect_route_methods(app)
    for path, methods in MVP_LIFECYCLE_ROUTES:
        assert methods <= present[path]

    # Structured responses use shared v3 models where attached.
    models = collect_route_response_models(app)
    assert models[("/v3/harvests", "POST")] is HarvestResponse
    assert models[("/v3/arcs", "POST")] is ArcResponse
    assert models[("/v3/liveness", "GET")] is LivenessResponse
