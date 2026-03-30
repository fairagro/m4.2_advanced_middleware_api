"""Modular V3 system endpoints using APIRouter."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from middleware.api.api.common.dependencies import get_accept_type, get_health_service
from middleware.api.health_service import ApiHealthService
from middleware.shared.api_models.v3.models import (
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
    StatusResponse,
)

router = APIRouter(prefix="/v3", tags=["v3", "system"])


@router.get("/liveness", response_model=LivenessResponse)
async def liveness(
    health_service: Annotated[ApiHealthService, Depends(get_health_service)],
    _: Annotated[None, Depends(get_accept_type)],
) -> LivenessResponse:
    """Return API process liveness status."""
    checks = await health_service.liveness_checks()
    return LivenessResponse(
        status=StatusResponse.OK if all(checks.values()) else StatusResponse.ERROR,
        services=checks,
    )


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    health_service: Annotated[ApiHealthService, Depends(get_health_service)],
    _: Annotated[None, Depends(get_accept_type)],
) -> ReadinessResponse:
    """Return API readiness based on direct dependencies."""
    checks = await health_service.readiness_checks()
    is_ready = all(checks.values()) if checks else True

    if not is_ready:
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status=StatusResponse.OK if is_ready else StatusResponse.ERROR,
        services=checks,
    )


@router.get("/health", response_model=HealthResponse)
async def health(
    response: Response,
    health_service: Annotated[ApiHealthService, Depends(get_health_service)],
    _: Annotated[None, Depends(get_accept_type)],
) -> HealthResponse:
    """Return global health for monitoring consumers."""
    checks = await health_service.global_health_checks()
    is_healthy = all(checks.values()) if checks else True

    if not is_healthy:
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE

    return HealthResponse(
        status=StatusResponse.OK if is_healthy else StatusResponse.ERROR,
        services=checks,
    )
