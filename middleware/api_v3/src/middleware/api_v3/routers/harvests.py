"""Shared FastAPI harvest lifecycle routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from middleware.api_v3.deps import get_lifecycle_port
from middleware.shared.api_models.v3 import models as v3_models
from middleware.shared.v3_lifecycle import HarvestArcLifecyclePort

router = APIRouter(prefix="/v3/harvests", tags=["v3", "harvests"])


@router.post("", response_model=v3_models.HarvestResponse)
async def create_harvest(
    response: Response,
    request_body: v3_models.CreateHarvestRequest,
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> v3_models.HarvestResponse:
    """Start a new harvest run."""
    outcome = await port.create_harvest(request_body, idempotency_key=idempotency_key)
    if outcome.replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return outcome.harvest


@router.get("/{harvest_id}", response_model=v3_models.HarvestResponse)
async def get_harvest(
    harvest_id: str,
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
) -> v3_models.HarvestResponse:
    """Get harvest details."""
    return await port.get_harvest(harvest_id)


@router.post("/{harvest_id}/complete", response_model=v3_models.HarvestResponse, deprecated=True)
async def complete_harvest(
    harvest_id: str,
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
) -> v3_models.HarvestResponse:
    """Mark a harvest as completed. [DEPRECATED].

    Use ``PATCH /v3/harvests/{harvest_id}`` with ``status=COMPLETED`` instead.
    """
    return await port.complete_harvest(harvest_id)


@router.patch("/{harvest_id}", response_model=v3_models.HarvestResponse)
async def patch_harvest_status(
    harvest_id: str,
    request_body: v3_models.PatchHarvestRequest,
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
) -> v3_models.HarvestResponse:
    """Transition a harvest run to a terminal status (COMPLETED, CANCELLED, or FAILED)."""
    return await port.patch_harvest(harvest_id, request_body)


@router.post("/{harvest_id}/arcs", response_model=v3_models.ArcResponse)
async def submit_arc_in_harvest(
    harvest_id: str,
    request_body: v3_models.SubmitHarvestArcRequest,
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
) -> v3_models.ArcResponse:
    """Submit an ARC within a harvest context."""
    return await port.submit_arc_in_harvest(harvest_id, request_body)
