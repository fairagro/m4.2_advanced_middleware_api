"""Modular V1 ARC endpoints using APIRouter."""

import logging
import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from middleware.api.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_business_logic,
    get_client_id,
    get_common_deps,
    get_content_type,
)
from middleware.api.business_logic import ArcOperationResult, BusinessLogic
from middleware.shared.api_models.v1 import models as v1_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/arcs", tags=["v1", "arcs"], deprecated=True)


@router.post("", status_code=HTTPStatus.ACCEPTED, response_model=v1_models.CreateOrUpdateArcsResponse)
async def create_or_update_arcs(
    request: Request,
    request_body: v1_models.CreateOrUpdateArcsRequest,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str, Depends(get_client_id)],
    _: Annotated[None, Depends(get_content_type)],
    __: Annotated[None, Depends(get_accept_type)],
) -> v1_models.CreateOrUpdateArcsResponse:
    """Submit ARCs for processing asynchronously (v1)."""
    rdi = request_body.rdi
    await deps.validate_rdi_authorized(rdi, request)

    if len(request_body.arcs) != 1:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Currently only single ARC submission is supported per request."
        )

    arc_data = request_body.arcs[0]
    result = await bl.create_or_update_arc(rdi, arc_data, client_id)

    task_id = str(uuid.uuid4())
    if isinstance(result, ArcOperationResult):
        bl.store_task_result(task_id, result)
    else:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unexpected result type")

    return v1_models.CreateOrUpdateArcsResponse(task_id=task_id, status="processing")
