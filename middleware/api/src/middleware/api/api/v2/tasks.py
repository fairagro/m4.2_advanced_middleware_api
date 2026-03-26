"""Modular V2 Task endpoints using APIRouter."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from middleware.api.api.common.dependencies import (
    get_accept_type,
    get_task_status_store,
)
from middleware.api.api.legacy.task_status_store import LegacyTaskStatusStore
from middleware.api.api.legacy.task_types import SyncTaskStatus
from middleware.shared.api_models.common.models import TaskStatus
from middleware.shared.api_models.v2 import models as v2_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/tasks", tags=["v2", "tasks"])


@router.get("/{task_id}", response_model=v2_models.GetTaskStatusResponse)
async def get_task_status_v2(
    task_id: str,
    task_status_store: Annotated[LegacyTaskStatusStore, Depends(get_task_status_store)],
    _: Annotated[None, Depends(get_accept_type)],
) -> v2_models.GetTaskStatusResponse:
    """Get the status of an async task (v2)."""
    result = await task_status_store.get_task_status(task_id)

    task_result: v2_models.ArcOperationResult | None = None
    error_message = None

    if result.status == SyncTaskStatus.SUCCESS:
        try:
            task_result = v2_models.ArcOperationResult.model_validate(result.result)
        except ValidationError as e:
            logger.error("Failed to validate task result for v2 request: %s", e)
    elif result.status == SyncTaskStatus.FAILURE:
        error_message = result.error

    # Map domain status to shared TaskStatus for the response model
    _status_map: dict[SyncTaskStatus, TaskStatus] = {
        SyncTaskStatus.PENDING: TaskStatus.PENDING,
        SyncTaskStatus.RUNNING: TaskStatus.STARTED,
        SyncTaskStatus.SUCCESS: TaskStatus.SUCCESS,
        SyncTaskStatus.FAILURE: TaskStatus.FAILURE,
    }
    status = _status_map.get(result.status, TaskStatus.PENDING)

    return v2_models.GetTaskStatusResponse(
        status=status,
        result=task_result,
        message=error_message or "",
        client_id=task_result.client_id if task_result else None,
    )
