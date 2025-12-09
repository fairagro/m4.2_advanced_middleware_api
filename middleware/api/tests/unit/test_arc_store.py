"""Tests for ArcStore interface and error handling."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from middleware.api.arc_store import ArcStore, ArcStoreError


def create_mock_arc_store() -> ArcStore:
    """Create a mock ArcStore instance by patching abstract methods."""

    class ConcreteArcStore(ArcStore):
        arc_id = MagicMock()

        async def _create_or_update(self, *_args: object, **_kwargs: object) -> None:
            pass

        def _delete(self, *_args: object, **_kwargs: object) -> None:
            pass

        def _exists(self, *_args: object, **_kwargs: object) -> bool:
            return False

        def _get(self, *_args: object, **_kwargs: object) -> object:
            pass

    return ConcreteArcStore()


class TestArcStoreError:
    """Test suite for ArcStoreError exception."""

    def test_arc_store_error_is_exception(self) -> None:
        """Test that ArcStoreError is an Exception."""
        error = ArcStoreError("Test error")
        assert isinstance(error, Exception)

    def test_arc_store_error_message(self) -> None:
        """Test ArcStoreError message."""
        message = "Test error message"
        error = ArcStoreError(message)
        assert str(error) == message


class TestArcStoreWrapperMethods:
    """Test suite for ArcStore wrapper methods that handle errors."""

    def test_create_or_update_arc_store_error_passthrough(self) -> None:
        """Test create_or_update passes through ArcStoreError."""
        store = create_mock_arc_store()
        with patch.object(store, "_create_or_update") as mock_impl:
            mock_impl.side_effect = ArcStoreError("Test error")
            with pytest.raises(ArcStoreError):
                asyncio.run(store.create_or_update("test_id", MagicMock()))

    def test_get_arc_store_error_passthrough(self) -> None:
        """Test get passes through ArcStoreError."""
        store = create_mock_arc_store()
        with patch.object(store, "_get", side_effect=ArcStoreError("Test error")), pytest.raises(ArcStoreError):
            store.get("test_id")

    def test_get_generic_exception_logged_and_reraised(self) -> None:
        """Test get logs and re-raises generic exceptions."""
        store = create_mock_arc_store()
        with (
            patch.object(store, "_get", side_effect=ValueError("Generic error")),
            patch("middleware.api.arc_store.logger") as mock_logger,
        ):
            with pytest.raises(ValueError):
                store.get("test_id")
            mock_logger.exception.assert_called_once()

    def test_delete_arc_store_error_passthrough(self) -> None:
        """Test delete passes through ArcStoreError."""
        store = create_mock_arc_store()
        with patch.object(store, "_delete", side_effect=ArcStoreError("Test error")), pytest.raises(ArcStoreError):
            store.delete("test_id")

    def test_delete_generic_exception_wrapped(self) -> None:
        """Test delete wraps generic exceptions in ArcStoreError."""
        store = create_mock_arc_store()
        with patch.object(store, "_delete", side_effect=RuntimeError("Generic error")):
            with pytest.raises(ArcStoreError) as exc_info:
                store.delete("test_id")
            assert "general exception caught" in str(exc_info.value).lower()

    def test_exists_arc_store_error_passthrough(self) -> None:
        """Test exists passes through ArcStoreError."""
        store = create_mock_arc_store()
        with patch.object(store, "_exists", side_effect=ArcStoreError("Test error")), pytest.raises(ArcStoreError):
            store.exists("test_id")

    def test_exists_generic_exception_wrapped(self) -> None:
        """Test exists wraps generic exceptions in ArcStoreError."""
        store = create_mock_arc_store()
        with patch.object(store, "_exists", side_effect=OSError("Generic error")):
            with pytest.raises(ArcStoreError) as exc_info:
                store.exists("test_id")
            assert "exception" in str(exc_info.value).lower()

    def test_exists_generic_exception_logged(self) -> None:
        """Test exists logs exceptions."""
        store = create_mock_arc_store()
        with (
            patch.object(store, "_exists", side_effect=OSError("Generic error")),
            patch("middleware.api.arc_store.logger") as mock_logger,
        ):
            with pytest.raises(ArcStoreError):
                store.exists("test_id")
            mock_logger.exception.assert_called_once()
