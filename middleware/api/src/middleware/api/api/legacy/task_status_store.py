"""Legacy task status store for v1/v2 endpoints backed by DocumentStore."""

import asyncio
import logging
import threading
from collections.abc import Coroutine
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any

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


class _DocumentStoreSyncBridge:
    """Run async DocumentStore operations from synchronous legacy call sites."""

    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        with cls._lock:
            if cls._loop is not None:
                return cls._loop

            loop = asyncio.new_event_loop()

            def _runner() -> None:
                asyncio.set_event_loop(loop)
                loop.run_forever()

            thread = threading.Thread(target=_runner, name="legacy-task-status-sync-bridge", daemon=True)
            thread.start()
            cls._loop = loop
            cls._thread = thread
            return loop

    @classmethod
    def run(cls, coroutine: Coroutine[Any, Any, Any], timeout_seconds: float) -> object:
        """Execute coroutine on bridge loop and return result."""
        loop = cls._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        return future.result(timeout=timeout_seconds)


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

    def get_task_status(self, task_id: str) -> SyncTaskResult:
        """Read task status record from document storage."""
        try:
            record = _DocumentStoreSyncBridge.run(self._doc_store.get_task_record(task_id), timeout_seconds=2.0)
        except (FuturesTimeoutError, RuntimeError, ValueError, OSError) as exc:
            logger.warning("Task status read failed for %s: %s", task_id, exc)
            return SyncTaskResult(status=SyncTaskStatus.PENDING)

        if not isinstance(record, TaskRecord):
            return SyncTaskResult(status=SyncTaskStatus.PENDING)

        mapped_status = SyncTaskStatus(record.status.value)

        if mapped_status == SyncTaskStatus.SUCCESS:
            result_payload = record.result.model_dump(mode="json") if record.result is not None else None
            return SyncTaskResult(status=SyncTaskStatus.SUCCESS, result=result_payload)
        if mapped_status == SyncTaskStatus.FAILURE:
            return SyncTaskResult(status=SyncTaskStatus.FAILURE, error=record.error or "Task failed")
        if mapped_status == SyncTaskStatus.RUNNING:
            return SyncTaskResult(status=SyncTaskStatus.RUNNING)
        return SyncTaskResult(status=SyncTaskStatus.PENDING)

    def store_task_result(self, task_id: str, result: ArcOperationResult) -> None:
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
            _DocumentStoreSyncBridge.run(
                self._doc_store.save_task_record(task_record=record),
                timeout_seconds=2.0,
            )
        except (FuturesTimeoutError, RuntimeError, ValueError, OSError) as exc:
            logger.warning("Task status write failed for %s: %s", task_id, exc)
