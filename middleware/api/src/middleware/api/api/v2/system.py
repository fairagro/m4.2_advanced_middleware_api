"""Modular V2 System endpoints using APIRouter."""

import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from middleware.api.api.common.dependencies import (
    get_accept_type,
    get_business_logic,
)
from middleware.api.business_logic import BusinessLogic
from middleware.shared.api_models.v2 import models as v2_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2", tags=["v2", "system"])


@router.get("/health", response_model=v2_models.HealthResponse)
async def health_check_v2(
    response: Response,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v2_models.HealthResponse:
    """Detailed health check for v2."""
    services = await bl.health_check()
    is_healthy = all(services.values())

    if not is_healthy:
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE

    return v2_models.HealthResponse(
        status="ok" if is_healthy else "error",
        services=services,
    )
