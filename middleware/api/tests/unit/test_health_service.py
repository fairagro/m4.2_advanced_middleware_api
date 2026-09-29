"""Unit tests for ApiHealthService dependency checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.health_service import ApiHealthService


@pytest.mark.asyncio
async def test_git_backend_fallback_closes_doc_store_when_create_arc_stores_fails() -> None:
    """Legacy fallback closes CouchDB even when ArcStore construction fails."""
    doc_store = MagicMock()
    doc_store.close = AsyncMock()
    config = MagicMock()
    config.consolidated_store = None

    with (
        patch("middleware.api.health_service.CouchDB", return_value=doc_store),
        patch(
            "middleware.api.health_service.create_arc_stores",
            side_effect=ValueError("invalid arc_store config"),
        ),
    ):
        service = ApiHealthService(config, MagicMock(), MagicMock(), arc_store=None)
        results = await service._check_git_backends()

    assert results["git_backend"] is False
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
    config.consolidated_store = None

    with (
        patch("middleware.api.health_service.CouchDB", return_value=doc_store),
        patch("middleware.api.health_service.create_arc_stores", return_value=(store, None)),
        patch("middleware.api.health_service.asyncio.to_thread", new=AsyncMock(return_value=True)),
    ):
        service = ApiHealthService(config, MagicMock(), MagicMock(), arc_store=None)
        results = await service._check_git_backends()

    assert results == {"git_backend": True}
    store.shutdown.assert_awaited_once()
    doc_store.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_git_backends_include_consolidated_when_configured() -> None:
    """Both slots appear in health when consolidated_store is wired."""
    arc_store = MagicMock()
    arc_store.check_health = MagicMock(return_value=True)
    consol = MagicMock()
    consol.check_health = MagicMock(return_value=False)
    config = MagicMock()
    config.health_checks.global_health_check_workers = False
    config.health_checks.global_health_check_git_backend = True
    config.health_checks.readiness_check_couchdb = False
    config.health_checks.readiness_check_rabbitmq = False

    with patch("middleware.api.health_service.asyncio.to_thread", new=AsyncMock(side_effect=[True, False])):
        service = ApiHealthService(
            config,
            MagicMock(),
            MagicMock(),
            arc_store=arc_store,
            consolidated_store=consol,
        )
        checks = await service.global_health_checks()

    assert checks["git_backend"] is True
    assert checks["consolidated_store"] is False
