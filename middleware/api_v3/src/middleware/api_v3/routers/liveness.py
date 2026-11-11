"""Shared FastAPI liveness probe."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from middleware.api_v3.deps import get_lifecycle_port
from middleware.shared.api_models.v3.models import LivenessResponse
from middleware.shared.v3_lifecycle import HarvestArcLifecyclePort

router = APIRouter(prefix="/v3", tags=["v3", "system"])


@router.get("/liveness", response_model=LivenessResponse)
async def liveness(
    port: Annotated[HarvestArcLifecyclePort, Depends(get_lifecycle_port)],
) -> LivenessResponse:
    """Return API process liveness status."""
    return await port.liveness()
