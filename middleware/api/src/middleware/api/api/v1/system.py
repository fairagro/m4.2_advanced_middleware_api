"""Modular V1 System endpoints using APIRouter."""

import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from middleware.api.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_business_logic,
    get_client_id,
    get_common_deps,
)
from middleware.api.business_logic import BusinessLogic
from middleware.shared.api_models.v1 import models as v1_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1", "system"], deprecated=True)


@router.get(
    "/whoami",
    response_model=v1_models.WhoamiResponse,
    deprecated=True,
    summary="Identify client (deprecated — use GET /v3/whoami)",
)
async def whoami(
    request: Request,
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.WhoamiResponse:
    """Identify the current client and authorized RDIs. Prefer ``GET /v3/whoami``."""
    authorized_rdis = await deps.get_authorized_rdis(request)
    known_rdis = deps.get_known_rdis()
    accessible_rdis = list(set(authorized_rdis) & set(known_rdis))

    return v1_models.WhoamiResponse(
        client_id=client_id,
        message="Client authenticated successfully",
        accessible_rdis=accessible_rdis,
    )


@router.get(
    "/liveness",
    response_model=v1_models.LivenessResponse,
    deprecated=True,
    summary="Liveness probe (deprecated — use GET /v3/liveness)",
    description=("Returns `{message}` only. Prefer `GET /v3/liveness`, which returns `{status, services}` instead."),
)
async def liveness(
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.LivenessResponse:
    """Return simple liveness (`{message}`). Prefer ``/v3/liveness`` (`{status, services}`)."""
    return v1_models.LivenessResponse()


@router.get(
    "/health",
    response_model=v1_models.HealthResponse,
    deprecated=True,
    summary="Health check (deprecated — use GET /v3/health or /v3/readiness)",
    description=(
        "Returns `{status, rabbitmq_reachable}` only. Prefer `GET /v3/readiness` / "
        "`GET /v3/health`, which expose a `services` map and split readiness from "
        "global health."
    ),
)
async def health_check(
    response: Response,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.HealthResponse:
    """Return v1 health (`rabbitmq_reachable`). Prefer ``/v3/readiness`` / ``/v3/health``."""
    services = await bl.health_check()
    is_healthy = all(services.values())

    if not is_healthy:
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE

    return v1_models.HealthResponse.model_validate({
        "status": "ok" if is_healthy else "error",
        "rabbitmq_reachable": services.get("rabbitmq", False),
    })
