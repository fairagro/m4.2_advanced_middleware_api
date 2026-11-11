"""Modular V3 system endpoints using APIRouter."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from middleware.api.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_client_id,
    get_common_deps,
    get_health_service,
)
from middleware.api.health_service import ApiHealthService
from middleware.api.package_version import resolve_api_package_version
from middleware.shared.api_models.v3.models import (
    HealthResponse,
    ReadinessResponse,
    StatusResponse,
    VersionResponse,
    WhoamiResponse,
)

router = APIRouter(prefix="/v3", tags=["v3", "system"])


@router.api_route("/version", methods=["GET", "HEAD"], response_model=VersionResponse)
async def package_version(
    _: Annotated[None, Depends(get_accept_type)],
) -> VersionResponse:
    """Return the installed api package PEP 440 version."""
    return VersionResponse(version=resolve_api_package_version())


@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(
    request: Request,
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
    _: Annotated[None, Depends(get_accept_type)],
) -> WhoamiResponse:
    """Identify the current client and authorized RDIs."""
    authorized_rdis = await deps.get_authorized_rdis(request)
    known_rdis = deps.get_known_rdis()
    accessible_rdis = list(set(authorized_rdis) & set(known_rdis))

    return WhoamiResponse(
        client_id=client_id,
        message="Client authenticated successfully",
        accessible_rdis=accessible_rdis,
    )


# GET /v3/liveness is registered by middleware.api_v3 (shared lifecycle surface).


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


@router.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
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
        version=resolve_api_package_version(),
    )
