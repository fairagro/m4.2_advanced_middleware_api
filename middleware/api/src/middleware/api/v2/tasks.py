"""Modular V2 Task endpoints using APIRouter."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from middleware.api.business_logic import BusinessLogic
from middleware.api.common.dependencies import (
    get_accept_type,
    get_business_logic,
)
from middleware.shared.api_models.v2 import models as v2_models
from middleware.shared.api_models.common.models import TaskStatus
from pydantic import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/tasks", tags=["v2", "tasks"])


@router.get("/{task_id}", response_model=v2_models.GetTaskStatusResponse)
async def get_task_status_v2(
    task_id: str,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v2_models.GetTaskStatusResponse:
    """Get the status of an async task (v2)."""
    result = bl.get_task_status(task_id)

    task_result: v2_models.ArcOperationResult | None = None
    error_message = None

    if result.ready():
        if result.successful():
            try:
                task_result = v2_models.ArcOperationResult.model_validate(result.result)
            except ValidationError as e:
                logger.error("Failed to validate task result for v2 request: %s", e)
        elif result.failed():
            error_message = str(result.result)

    # Map Celery status to TaskStatus
    status = TaskStatus.SUCCESS if result.successful() else (TaskStatus.FAILED if result.failed() else TaskStatus.PENDING)

    return v2_models.GetTaskStatusResponse(
        status=status,
        result=task_result,
    )
