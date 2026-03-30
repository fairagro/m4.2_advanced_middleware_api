"""Unit tests for Celery worker tasks."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.worker.worker import sync_arc_to_gitlab


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
        mock_bl.sync_to_gitlab.assert_called_once_with("test-rdi", {"dummy": "data"})


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
