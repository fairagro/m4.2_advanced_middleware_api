"""Shared FastAPI standalone ARC upload route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from middleware.api_v3.deps import get_lifecycle_port
from middleware.shared.api_models.v3 import models as v3_models
from middleware.shared.v3_lifecycle import HarvestArcLifecyclePort

router = APIRouter(prefix="/v3/arcs", tags=["v3", "arcs"])


@router.post("", response_model=v3_models.ArcResponse)
async def create_or_update_arc(
    request_body: v3_models.CreateArcRequest,
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
) -> v3_models.ArcResponse:
    """Process an ARC and return the result directly."""
    return await port.create_or_update_arc(request_body)
