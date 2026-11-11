"""Production-only V3 harvest endpoints (list + deprecated cancel).

Create/get/patch/complete/submit-arc lifecycle routes live in ``middleware.api_v3``.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from middleware.api.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_business_logic,
    get_client_id,
    get_common_deps,
)
from middleware.api.api.v3.lifecycle_port import _map_harvest
from middleware.api.business_logic import BusinessLogic
from middleware.shared.api_models.v3 import models as v3_models

router = APIRouter(prefix="/v3/harvests", tags=["v3", "harvests"])


@router.get("", response_model=list[v3_models.HarvestResponse])
async def list_harvests(  # noqa: PLR0913, PLR0917
    request: Request,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    _client_id: Annotated[str | None, Depends(get_client_id)],
    _accept_type: Annotated[None, Depends(get_accept_type)],
    rdi: str | None = None,
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
) -> list[v3_models.HarvestResponse]:
    """List harvest runs."""
    if rdi:
        await deps.validate_rdi_authorized(rdi, request)

    harvests = await bl.harvest_manager.list_harvests(rdi, skip=skip, limit=limit)
    return [_map_harvest(h) for h in harvests]


@router.delete("/{harvest_id}", status_code=HTTPStatus.NO_CONTENT, deprecated=True)
async def cancel_harvest(
    request: Request,
    harvest_id: str,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
) -> None:
    """Cancel a harvest run. [DEPRECATED].

    Use ``PATCH /v3/harvests/{harvest_id}`` with ``status=CANCELLED`` instead.
    """
    harvest = await bl.harvest_manager.get_harvest(harvest_id)
    if not harvest:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")

    await deps.validate_rdi_authorized(harvest.rdi, request)
    await bl.harvest_manager.cancel_harvest(harvest, client_id=client_id)
