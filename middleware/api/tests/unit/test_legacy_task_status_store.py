"""Unit tests for legacy task status store behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api.api.legacy.task_status_store import LegacyTaskStatusStore
from middleware.api.api.legacy.task_types import SyncTaskStatus


@pytest.mark.asyncio
async def test_get_task_status_returns_failure_on_read_timeout() -> None:
    """Timeouts from backend status lookup should surface as FAILURE."""
    doc_store = MagicMock()
    doc_store.get_task_record = AsyncMock(side_effect=TimeoutError)
    store = LegacyTaskStatusStore(doc_store=doc_store)

    result = await store.get_task_status("task-1")

    assert result.status == SyncTaskStatus.FAILURE
    assert result.error == "Task status lookup timed out"


@pytest.mark.asyncio
async def test_get_task_status_returns_failure_on_backend_error() -> None:
    """Backend read errors should not be masked as PENDING."""
    doc_store = MagicMock()
    doc_store.get_task_record = AsyncMock(side_effect=RuntimeError("boom"))
    store = LegacyTaskStatusStore(doc_store=doc_store)

    result = await store.get_task_status("task-1")

    assert result.status == SyncTaskStatus.FAILURE
    assert result.error == "Task status lookup failed"


@pytest.mark.asyncio
async def test_store_task_result_uses_document_store_once() -> None:
    """Storing a result should call save_task_record exactly once."""
    doc_store = MagicMock()
    doc_store.save_task_record = AsyncMock()
    store = LegacyTaskStatusStore(doc_store=doc_store)

    arc = MagicMock(id="arc-1", status=MagicMock(value="created"), timestamp="2026-03-25T14:39:20Z")
    result = MagicMock(client_id=None, message="ok", rdi="rdi-1", arc=arc)

    await store.store_task_result("task-1", result)

    doc_store.save_task_record.assert_awaited_once()
