"""Unit tests for ApiHealthService dependency checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.health_service import ApiHealthService


@pytest.mark.asyncio
async def test_git_backend_fallback_closes_doc_store_when_create_arc_store_fails() -> None:
    """Legacy fallback closes CouchDB even when ArcStore construction fails."""
    doc_store = MagicMock()
    doc_store.close = AsyncMock()
    config = MagicMock()

    with (
        patch("middleware.api.health_service.CouchDB", return_value=doc_store),
        patch(
            "middleware.api.health_service.create_arc_store",
            side_effect=ValueError("invalid arc_store config"),
        ),
    ):
        service = ApiHealthService(config, MagicMock(), MagicMock(), arc_store=None)
        healthy = await service._check_git_backend()

    assert healthy is False
    doc_store.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_git_backend_fallback_shuts_down_store_and_closes_doc_store() -> None:
    """Legacy fallback cleans up ArcStore and CouchDB on success."""
    doc_store = MagicMock()
    doc_store.close = AsyncMock()
    store = MagicMock()
    store.check_health = MagicMock(return_value=True)
    store.shutdown = AsyncMock()
    config = MagicMock()

    with (
        patch("middleware.api.health_service.CouchDB", return_value=doc_store),
        patch("middleware.api.health_service.create_arc_store", return_value=store),
        patch("middleware.api.health_service.asyncio.to_thread", new=AsyncMock(return_value=True)),
    ):
        service = ApiHealthService(config, MagicMock(), MagicMock(), arc_store=None)
        healthy = await service._check_git_backend()

    assert healthy is True
    store.shutdown.assert_awaited_once()
    doc_store.close.assert_awaited_once()
