"""Unit tests for Celery worker tasks."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.worker.worker import _celery_retries_exhausted, finalize_catalog, sync_arc_to_gitlab


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
    with patch("middleware.api.worker.worker.BusinessLogicManager.get") as mock_get:
        mock_bl = MagicMock()
        mock_bl.sync_to_gitlab = AsyncMock()
        loop = asyncio.new_event_loop()
        mock_get.return_value = (mock_bl, loop)

        try:
            result = sync_arc_to_gitlab.apply(
                args=({"rdi": "test-rdi", "arc": {"dummy": "data"}, "client_id": "test-client"},)
            ).get()
        finally:
            loop.close()

        assert result is None
        mock_bl.sync_to_gitlab.assert_called_once_with(
            "test-rdi",
            {"dummy": "data"},
            record_transient_as_failed=False,
        )


def test_sync_arc_to_gitlab_passes_exhausted_flag() -> None:
    """On the final Celery attempt, record_transient_as_failed is True."""
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
            sync_arc_to_gitlab.apply(
                args=({"rdi": "test-rdi", "arc": {"dummy": "data"}, "client_id": "test-client"},)
            ).get()
        finally:
            loop.close()

        mock_bl.sync_to_gitlab.assert_called_once_with(
            "test-rdi",
            {"dummy": "data"},
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


def test_sync_arc_to_gitlab_failure() -> None:
    """Test task failure handling — exception must be re-raised."""
    with patch("middleware.api.worker.worker.BusinessLogicManager.get") as mock_get:
        mock_bl = MagicMock()
        mock_bl.sync_to_gitlab = AsyncMock(side_effect=ValueError("Processing failed"))
        loop = asyncio.new_event_loop()
        mock_get.return_value = (mock_bl, loop)

        try:
            with pytest.raises(ValueError, match="Processing failed"):
                sync_arc_to_gitlab.apply(
                    args=({"rdi": "test-rdi", "arc": {"dummy": "data"}, "client_id": "test-client"},)
                ).get()
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
            args=({"rdi": "test-rdi", "arc": {"dummy": "data"}, "client_id": "test-client"},)
        ).get()
