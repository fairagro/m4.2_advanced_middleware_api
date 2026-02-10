"""Unit tests for Celery worker tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.worker import sync_arc_to_gitlab


def test_sync_arc_to_gitlab_success() -> None:
    """Test successful task execution."""
    # Mock business logic result (sync_to_gitlab returns None)

    # Mock get_business_logic
    with patch("middleware.api.worker.BusinessLogicManager.get_business_logic") as mock_get_bl:
        mock_bl = MagicMock()
        mock_get_bl.return_value = mock_bl
        # Mock context manager
        mock_bl.__aenter__ = AsyncMock(return_value=mock_bl)
        mock_bl.__aexit__ = AsyncMock(return_value=False)

        mock_bl.sync_to_gitlab = AsyncMock()

        # Execute the task
        # Note: client_id is no longer passed to sync_arc_to_gitlab
        result = sync_arc_to_gitlab.apply(args=("test-rdi", {"dummy": "data"})).get()

        # Verify result dictionary structure
        assert result["status"] == "synced"
        assert result["message"] == "Successfully synced to GitLab"
        assert result["rdi"] == "test-rdi"

        mock_bl.sync_to_gitlab.assert_called_once_with("test-rdi", {"dummy": "data"})


def test_sync_arc_to_gitlab_failure() -> None:
    """Test task failure handling."""
    with patch("middleware.api.worker.BusinessLogicManager.get_business_logic") as mock_get_bl:
        mock_bl = MagicMock()
        mock_get_bl.return_value = mock_bl
        # Mock context manager
        mock_bl.__aenter__ = AsyncMock(return_value=mock_bl)
        mock_bl.__aexit__ = AsyncMock(return_value=False)

        # Set sync_to_gitlab as AsyncMock with side_effect
        mock_bl.sync_to_gitlab = AsyncMock(side_effect=ValueError("Processing failed"))

        with pytest.raises(ValueError, match="Processing failed"):
            sync_arc_to_gitlab.apply(args=("test-rdi", {"dummy": "data"})).get()


def test_sync_arc_to_gitlab_no_business_logic() -> None:
    """Test task fails when business_logic is not initialized."""
    with (
        patch("middleware.api.worker.BusinessLogicManager.get_business_logic", return_value=None),
        pytest.raises(TypeError, match="'NoneType' object does not support the asynchronous context manager protocol"),
    ):
        sync_arc_to_gitlab.apply(args=("test-rdi", {"dummy": "data"})).get()
