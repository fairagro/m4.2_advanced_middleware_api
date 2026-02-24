"""Modular V2 System endpoints using APIRouter."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from middleware.api.business_logic import BusinessLogic
from middleware.api.common.dependencies import (
    get_business_logic,
)
from middleware.shared.api_models.v2 import models as v2_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2", tags=["v2", "system"])


@router.get("/health", response_model=v2_models.HealthResponse)
async def health_check_v2(
    response: Response,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
) -> v2_models.HealthResponse:
    """Detailed health check for v2."""
    services = await bl.health_check()
    is_healthy = all(services.values())
    
    if not is_healthy:
        response.status_code = 503
        
    return v2_models.HealthResponse(
        status="ok" if is_healthy else "error",
        services=services,
    )
