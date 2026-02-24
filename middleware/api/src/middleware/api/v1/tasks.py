"""Modular V1 Task endpoints using APIRouter."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException
from middleware.api.business_logic import BusinessLogic
from middleware.api.common.dependencies import (
    get_accept_type,
    get_business_logic,
)
from middleware.shared.api_models.v1 import models as v1_models
from middleware.shared.api_models.common.models import ArcOperationResult
from pydantic import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tasks", tags=["v1", "tasks"])


@router.get("/{task_id}", response_model=v1_models.GetTaskStatusResponse)
async def get_task_status(
    task_id: str,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v1_models.GetTaskStatusResponse:
    """Get the status of an async task (v1)."""
    result = bl.get_task_status(task_id)

    task_result: v1_models.CreateOrUpdateArcsResponse | None = None
    error_message = None

    if result.ready():
        if result.successful():
            try:
                inner_res = ArcOperationResult.model_validate(result.result)
                task_result = v1_models.CreateOrUpdateArcsResponse(
                    client_id=inner_res.client_id,
                    rdi=inner_res.rdi,
                    message=inner_res.message,
                    arcs=[inner_res.arc] if inner_res.arc else [],
                )
            except ValidationError:
                try:
                    task_result = v1_models.CreateOrUpdateArcsResponse.model_validate(result.result)
                except ValidationError as e:
                    logger.error("Failed to validate task result for v1 request: %s", e)
        elif result.failed():
            error_message = str(result.result)

    return v1_models.GetTaskStatusResponse(
        task_id=task_id,
        status=result.status,
        result=task_result,
        error=error_message,
    )
