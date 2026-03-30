"""Legacy task status store for v1/v2 endpoints backed by DocumentStore."""

import asyncio
import logging
from datetime import datetime

from middleware.shared.api_models.common.models import ArcOperationResult

from ...document_store import DocumentStore
from ...document_store.task_record import (
    TaskArcOperationResult,
    TaskArcResponse,
    TaskArcStatus,
    TaskRecord,
    TaskRecordStatus,
)
from .task_types import SyncTaskResult, SyncTaskStatus

logger = logging.getLogger(__name__)

_TASK_STATUS_READ_TIMEOUT_SECONDS = 5.0
_TASK_STATUS_WRITE_TIMEOUT_SECONDS = 5.0


class LegacyTaskStatusStore:
    """Task status persistence adapter for v1/v2 endpoints."""

    def __init__(self, doc_store: DocumentStore) -> None:
        """Initialize adapter with backend-agnostic DocumentStore."""
        self._doc_store = doc_store

    @staticmethod
    def _parse_arc_timestamp(raw_timestamp: str) -> datetime:
        """Parse API ARC timestamp into a datetime for persistence."""
        normalized = raw_timestamp.strip()
        if normalized.endswith("Z"):
            # Keep an existing offset intact (e.g. "+00:00Z" -> "+00:00").
            if (
                len(normalized) >= 7  # noqa: PLR2004
                and normalized[-7] in "+-"
                and normalized[-6:-3].isdigit()
                and normalized[-3] == ":"
                and normalized[-2:].isdigit()
            ):
                normalized = normalized[:-1]
            else:
                normalized = f"{normalized[:-1]}+00:00"

        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            if normalized.endswith("+00:00+00:00"):
                return datetime.fromisoformat(normalized[:-6])
            raise

    async def get_task_status(self, task_id: str) -> SyncTaskResult:
        """Read task status record from document storage."""
        result: SyncTaskResult
        try:
            record = await asyncio.wait_for(
                self._doc_store.get_task_record(task_id),
                timeout=_TASK_STATUS_READ_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            logger.warning("Task status read timed out for %s: %s", task_id, exc)
            result = SyncTaskResult(status=SyncTaskStatus.FAILURE, error="Task status lookup timed out")
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning("Task status read failed for %s: %s", task_id, exc)
            result = SyncTaskResult(status=SyncTaskStatus.FAILURE, error="Task status lookup failed")
        else:
            if not isinstance(record, TaskRecord):
                result = SyncTaskResult(status=SyncTaskStatus.PENDING)
            else:
                mapped_status = SyncTaskStatus(record.status.value)

                if mapped_status == SyncTaskStatus.SUCCESS:
                    result_payload = record.result.model_dump(mode="json") if record.result is not None else None
                    result = SyncTaskResult(status=SyncTaskStatus.SUCCESS, result=result_payload)
                elif mapped_status == SyncTaskStatus.FAILURE:
                    result = SyncTaskResult(status=SyncTaskStatus.FAILURE, error=record.error or "Task failed")
                elif mapped_status == SyncTaskStatus.RUNNING:
                    result = SyncTaskResult(status=SyncTaskStatus.RUNNING)
                else:
                    result = SyncTaskResult(status=SyncTaskStatus.PENDING)

        return result

    async def store_task_result(self, task_id: str, result: ArcOperationResult) -> None:
        """Persist successful task result via DocumentStore abstraction."""
        record = TaskRecord(
            task_id=task_id,
            status=TaskRecordStatus.SUCCESS,
            result=TaskArcOperationResult(
                client_id=result.client_id,
                message=result.message,
                rdi=result.rdi,
                arc=TaskArcResponse(
                    id=result.arc.id,
                    status=TaskArcStatus(result.arc.status.value),
                    timestamp=self._parse_arc_timestamp(result.arc.timestamp),
                ),
            ),
        )
        try:
            await asyncio.wait_for(
                self._doc_store.save_task_record(task_record=record),
                timeout=_TASK_STATUS_WRITE_TIMEOUT_SECONDS,
            )
        except (TimeoutError, RuntimeError, ValueError, OSError) as exc:
            logger.error("Task status write failed for %s: %s", task_id, exc)
            raise
