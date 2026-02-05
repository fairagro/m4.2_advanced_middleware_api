"""Unit tests for Celery worker tasks."""

from typing import Any
from unittest.mock import patch, AsyncMock

import pytest

from middleware.api.worker import process_arc
from middleware.shared.api_models.models import (
    ArcOperationResult,
    ArcResponse,
    ArcStatus,
)


def test_process_arc_success() -> None:
    """Test successful task execution."""
    # Mock business logic result
    mock_result = ArcOperationResult(
        rdi="test-rdi",
        client_id="test-client",
        message="ok",
        arc=ArcResponse(id="arc-1", status=ArcStatus.CREATED, timestamp="2024-01-01T00:00:00Z"),
    )

    # Mock the business_logic from celery_app
    # Mock the business_logic from celery_app
    with patch("middleware.api.worker.business_logic") as mock_bl:
        mock_bl.connect = AsyncMock()
        mock_bl.close = AsyncMock()
        # Define the async return value
        async def async_return(*_args: Any, **_kwargs: Any) -> ArcOperationResult:
            return mock_result

        mock_bl.create_or_update_arc.side_effect = async_return

        # Execute the task
        result = process_arc.apply(args=("test-rdi", {"dummy": "data"}, "test-client")).get()

        # Verify result dictionary structure
        assert result["rdi"] == "test-rdi"
        assert result["client_id"] == "test-client"
        assert result["message"] == "ok"
        assert result["arc"]["id"] == "arc-1"


def test_process_arc_failure() -> None:
    """Test task failure handling."""
    with patch("middleware.api.worker.business_logic") as mock_bl:
        mock_bl.connect = AsyncMock()
        mock_bl.close = AsyncMock()
        # Define the async return value that raises an exception
        async def async_raise(*_args: Any, **_kwargs: Any) -> None:
            raise ValueError("Processing failed")

        mock_bl.create_or_update_arc.side_effect = async_raise

        with pytest.raises(ValueError, match="Processing failed"):
            process_arc.apply(args=("test-rdi", {"dummy": "data"}, "test-client")).get()


def test_process_arc_no_business_logic() -> None:
    """Test task fails when business_logic is not initialized."""
    with (
        patch("middleware.api.worker.business_logic", None),
        pytest.raises(RuntimeError, match="BusinessLogic not initialized"),
    ):
        process_arc.apply(args=("test-rdi", {"dummy": "data"}, "test-client")).get()
