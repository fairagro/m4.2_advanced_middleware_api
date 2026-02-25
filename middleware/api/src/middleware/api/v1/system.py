"""Modular V1 System endpoints using APIRouter."""

import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from middleware.api.business_logic import BusinessLogic
from middleware.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_business_logic,
    get_client_id,
    get_common_deps,
)
from middleware.shared.api_models.v1 import models as v1_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1", "system"])


@router.get("/whoami", response_model=v1_models.WhoamiResponse)
async def whoami(
    request: Request,
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.WhoamiResponse:
    """Identify the current client and authorized RDIs."""
    authorized_rdis = await deps.get_authorized_rdis(request)
    known_rdis = deps.get_known_rdis()
    accessible_rdis = list(set(authorized_rdis) & set(known_rdis))

    return v1_models.WhoamiResponse(
        client_id=client_id,
        message="Client authenticated successfully",
        accessible_rdis=accessible_rdis,
    )


@router.get("/liveness", response_model=v1_models.LivenessResponse)
async def liveness(
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.LivenessResponse:
    """Perform a simple liveness check."""
    return v1_models.LivenessResponse()


@router.get("/health", response_model=v1_models.HealthResponse)
async def health_check(
    response: Response,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.HealthResponse:
    """Detailed health check for v1."""
    services = await bl.health_check()
    is_healthy = all(services.values())

    if not is_healthy:
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE

    return v1_models.HealthResponse(
        status="ok" if is_healthy else "error",
        redis_reachable=services.get("redis", False),
        rabbitmq_reachable=services.get("rabbitmq", False),
    )
