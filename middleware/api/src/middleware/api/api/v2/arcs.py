"""Modular V2 ARC endpoints using APIRouter."""

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
    get_task_status_store,
)
from middleware.api.business_logic import ArcOperationResult, BusinessLogic
from middleware.shared.api_models.common.models import TaskStatus
from middleware.shared.api_models.v2 import models as v2_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/arcs", tags=["v2", "arcs"])


@router.post("", status_code=HTTPStatus.ACCEPTED, response_model=v2_models.CreateOrUpdateArcResponse)
async def create_or_update_arc(
    request: Request,
    request_body: v2_models.CreateOrUpdateArcRequest,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
    _: Annotated[None, Depends(get_content_type)],
    __: Annotated[None, Depends(get_accept_type)],
) -> v2_models.CreateOrUpdateArcResponse:
    """Submit a single ARC for processing asynchronously (v2)."""
    rdi = request_body.rdi
    await deps.validate_rdi_authorized(rdi, request)

    result = await bl.create_or_update_arc(rdi, request_body.arc, client_id)

    task_id = str(uuid.uuid4())
    if isinstance(result, ArcOperationResult):
        task_status_store = get_task_status_store(request)
        task_status_store.store_task_result(task_id, result)
    else:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unexpected result type")

    return v2_models.CreateOrUpdateArcResponse(
        task_id=task_id,
        status=TaskStatus.SUCCESS,
    )
