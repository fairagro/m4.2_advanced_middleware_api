"""Unit tests for Celery worker tasks."""

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.arc_store import ArcStoreTransientError
from middleware.api.business_logic import BusinessLogic, TransientError
from middleware.api.document_store.arc_document import ArcEventType
from middleware.api.worker.worker import _celery_retries_exhausted, finalize_catalog, sync_arc_to_gitlab


@contextmanager
def _low_celery_retries(task: Any, *, max_retries: int = 1) -> Iterator[None]:
    """Shrink Celery autoretry budget so exhaustion tests stay fast.

    Typed as ``Any`` because celery-stubs' ``Task`` omits ``retry_backoff`` /
    ``retry_jitter`` that exist on real task instances.
    """
    original_max = task.max_retries
    original_backoff = task.retry_backoff
    original_jitter = task.retry_jitter
    task.max_retries = max_retries
    task.retry_backoff = False
    task.retry_jitter = False
    try:
        yield
    finally:
        task.max_retries = original_max
        task.retry_backoff = original_backoff
        task.retry_jitter = original_jitter


def test_celery_retries_exhausted_on_final_attempt() -> None:
    """Final attempt is when request.retries equals max_retries."""
    task = MagicMock()
    task.max_retries = 3
    task.request.retries = 3
    assert _celery_retries_exhausted(task) is True


def test_celery_retries_exhausted_mid_retry() -> None:
    """Earlier attempts must not look exhausted."""
    task = MagicMock()
    task.max_retries = 3
    task.request.retries = 2
    assert _celery_retries_exhausted(task) is False


def test_celery_retries_exhausted_unlimited() -> None:
    """Unlimited max_retries never reports exhaustion."""
    task = MagicMock()
    task.max_retries = None
    task.request.retries = 99
    assert _celery_retries_exhausted(task) is False


def test_sync_arc_to_gitlab_success() -> None:
    """Test successful task execution."""
    arc_json = json.dumps({"dummy": "data"})
    with patch("middleware.api.worker.worker.BusinessLogicManager.get") as mock_get:
        mock_bl = MagicMock()
        mock_bl.sync_to_gitlab = AsyncMock()
        loop = asyncio.new_event_loop()
        mock_get.return_value = (mock_bl, loop)

        try:
            result = sync_arc_to_gitlab.apply(
                args=({"rdi": "test-rdi", "arc": arc_json, "client_id": "test-client"},)
            ).get()
        finally:
            loop.close()

        assert result is None
        mock_bl.sync_to_gitlab.assert_called_once_with(
            "test-rdi",
            arc_json,
            record_transient_as_failed=False,
        )


def test_sync_arc_to_gitlab_passes_exhausted_flag() -> None:
    """On the final Celery attempt, record_transient_as_failed is True."""
    arc_json = json.dumps({"dummy": "data"})
    with (
        patch("middleware.api.worker.worker.BusinessLogicManager.get") as mock_get,
        patch(
            "middleware.api.worker.worker._celery_retries_exhausted",
            return_value=True,
        ),
    ):
        mock_bl = MagicMock()
        mock_bl.sync_to_gitlab = AsyncMock()
        loop = asyncio.new_event_loop()
        mock_get.return_value = (mock_bl, loop)

        try:
            sync_arc_to_gitlab.apply(args=({"rdi": "test-rdi", "arc": arc_json, "client_id": "test-client"},)).get()
        finally:
            loop.close()

        mock_bl.sync_to_gitlab.assert_called_once_with(
            "test-rdi",
            arc_json,
            record_transient_as_failed=True,
        )


def test_finalize_catalog_passes_exhausted_flag() -> None:
    """On the final Celery attempt, finalize sets record_transient_as_failed."""
    with (
        patch("middleware.api.worker.worker.BusinessLogicManager.get") as mock_get,
        patch(
            "middleware.api.worker.worker._celery_retries_exhausted",
            return_value=True,
        ),
    ):
        mock_bl = MagicMock()
        mock_bl.finalize_catalog = AsyncMock()
        loop = asyncio.new_event_loop()
        mock_get.return_value = (mock_bl, loop)

        try:
            finalize_catalog.apply(
                args=(
                    {
                        "rdi": "test-rdi",
                        "harvest_id": "harvest-1",
                        "client_id": "test-client",
                    },
                )
            ).get()
        finally:
            loop.close()

        mock_bl.finalize_catalog.assert_called_once_with(
            "test-rdi",
            harvest_id="harvest-1",
            record_transient_as_failed=True,
        )


def test_sync_arc_to_gitlab_exhausted_retries_records_git_push_failed() -> None:
    """Celery autoretry exhaustion leaves exactly one durable GIT_PUSH_FAILED.

    Exercises the real worker → BusinessLogic → ArcManager path with Celery's
    retry counter (not a patched exhaustion flag). Mid-retry stays quiet.
    """
    mock_store = MagicMock()
    mock_store.create_or_update = AsyncMock(side_effect=ArcStoreTransientError("git down"))
    mock_store.shutdown = AsyncMock()
    mock_doc_store = MagicMock()
    mock_doc_store.add_event = AsyncMock()
    worker_logic = BusinessLogic(config=MagicMock(), store=mock_store, doc_store=mock_doc_store)
    loop = asyncio.new_event_loop()

    with (
        _low_celery_retries(sync_arc_to_gitlab, max_retries=1),
        patch(
            "middleware.api.worker.worker.BusinessLogicManager.get",
            return_value=(worker_logic, loop),
        ),
        patch("middleware.api.business_logic.arc_manager.ARC") as mock_arc,
        patch("middleware.api.business_logic.arc_manager.calculate_arc_id", return_value="arc_id"),
    ):
        mock_arc.from_rocrate_json_string.return_value = MagicMock(Identifier="ABC")
        try:
            with pytest.raises(TransientError, match="git down"):
                sync_arc_to_gitlab.apply(
                    args=(
                        {
                            "rdi": "test-rdi",
                            "arc": json.dumps(minimal_rocrate_dict("ABC")),
                            "client_id": "test-client",
                        },
                    )
                ).get()
        finally:
            loop.close()

    # First attempt (retries=0) + final attempt (retries=1)
    assert mock_store.create_or_update.await_count == 2
    mock_doc_store.add_event.assert_called_once()
    event = mock_doc_store.add_event.call_args.args[1]
    assert event.type == ArcEventType.GIT_PUSH_FAILED
    assert "git down" in event.message


def test_finalize_catalog_exhausted_retries_records_catalog_push_failed() -> None:
    """Celery autoretry exhaustion leaves exactly one durable CATALOG_PUSH_FAILED."""
    mock_store = MagicMock()
    mock_store.shutdown = AsyncMock()
    mock_consolidated = MagicMock()
    mock_consolidated.finalize = AsyncMock(side_effect=ArcStoreTransientError("git down"))
    mock_consolidated.shutdown = AsyncMock()
    mock_doc_store = MagicMock()
    mock_doc_store.update_harvest = AsyncMock()
    worker_logic = BusinessLogic(
        config=MagicMock(),
        store=mock_store,
        doc_store=mock_doc_store,
        consolidated_store=mock_consolidated,
    )
    loop = asyncio.new_event_loop()

    with (
        _low_celery_retries(finalize_catalog, max_retries=1),
        patch(
            "middleware.api.worker.worker.BusinessLogicManager.get",
            return_value=(worker_logic, loop),
        ),
    ):
        try:
            with pytest.raises(TransientError, match="git down"):
                finalize_catalog.apply(
                    args=(
                        {
                            "rdi": "test-rdi",
                            "harvest_id": "harvest-1",
                            "client_id": "test-client",
                        },
                    )
                ).get()
        finally:
            loop.close()

    assert mock_consolidated.finalize.await_count == 2
    mock_doc_store.update_harvest.assert_called_once()
    patch_body = mock_doc_store.update_harvest.call_args.args[1]
    assert patch_body["append_catalog_event"]["type"] == "CATALOG_PUSH_FAILED"
    assert "git down" in patch_body["append_catalog_event"]["message"]


def test_sync_arc_to_gitlab_failure() -> None:
    """Test task failure handling — exception must be re-raised."""
    arc_json = json.dumps({"dummy": "data"})
    with patch("middleware.api.worker.worker.BusinessLogicManager.get") as mock_get:
        mock_bl = MagicMock()
        mock_bl.sync_to_gitlab = AsyncMock(side_effect=ValueError("Processing failed"))
        loop = asyncio.new_event_loop()
        mock_get.return_value = (mock_bl, loop)

        try:
            with pytest.raises(ValueError, match="Processing failed"):
                sync_arc_to_gitlab.apply(args=({"rdi": "test-rdi", "arc": arc_json, "client_id": "test-client"},)).get()
        finally:
            loop.close()


def test_sync_arc_to_gitlab_initialization_error() -> None:
    """Test task fails (and re-raises) when BusinessLogicManager.get raises."""
    with (
        patch(
            "middleware.api.worker.worker.BusinessLogicManager.get",
            side_effect=RuntimeError("CouchDB unreachable"),
        ),
        pytest.raises(RuntimeError, match="CouchDB unreachable"),
    ):
        sync_arc_to_gitlab.apply(
            args=({"rdi": "test-rdi", "arc": json.dumps({"dummy": "data"}), "client_id": "test-client"},)
        ).get()
