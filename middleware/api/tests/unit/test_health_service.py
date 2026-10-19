"""Unit tests for ApiHealthService dependency checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.health_service import ApiHealthService


def _doc_store() -> MagicMock:
    store = MagicMock()
    store.health_check = AsyncMock(return_value=True)
    return store


@pytest.mark.asyncio
async def test_readiness_couchdb_uses_document_store_health() -> None:
    """Readiness uses document-store health (application DB)."""
    doc_store = _doc_store()
    doc_store.health_check = AsyncMock(return_value=False)
    config = MagicMock()
    config.health_checks.readiness_check_couchdb = True
    config.health_checks.readiness_check_rabbitmq = False

    service = ApiHealthService(
        config,
        MagicMock(),
        MagicMock(),
        document_store=doc_store,
    )
    checks = await service.readiness_checks()

    assert checks["couchdb_reachable"] is False
    doc_store.health_check.assert_awaited_once()


@pytest.mark.asyncio
async def test_git_backend_fallback_closes_doc_store_when_create_arc_stores_fails() -> None:
    """Legacy fallback closes CouchDB even when ArcStore construction fails."""
    transient_doc = MagicMock()
    transient_doc.close = AsyncMock()
    config = MagicMock()
    config.consolidated_store = None

    with (
        patch("middleware.api.health_service.CouchDB", return_value=transient_doc),
        patch(
            "middleware.api.health_service.create_arc_stores",
            side_effect=ValueError("invalid arc_store config"),
        ),
    ):
        service = ApiHealthService(config, MagicMock(), MagicMock(), document_store=_doc_store(), arc_store=None)
        results = await service._check_git_backends()

    assert results["git_backend"] is False
    transient_doc.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_git_backend_fallback_shuts_down_store_and_closes_doc_store() -> None:
    """Legacy fallback cleans up ArcStore and CouchDB on success."""
    transient_doc = MagicMock()
    transient_doc.close = AsyncMock()
    store = MagicMock()
    store.check_health = MagicMock(return_value=True)
    store.shutdown = AsyncMock()
    config = MagicMock()
    config.consolidated_store = None

    with (
        patch("middleware.api.health_service.CouchDB", return_value=transient_doc),
        patch("middleware.api.health_service.create_arc_stores", return_value=(store, None)),
        patch("middleware.api.health_service.asyncio.to_thread", new=AsyncMock(return_value=True)),
    ):
        service = ApiHealthService(config, MagicMock(), MagicMock(), document_store=_doc_store(), arc_store=None)
        results = await service._check_git_backends()

    assert results == {"git_backend": True}
    store.shutdown.assert_awaited_once()
    transient_doc.close.assert_awaited_once()


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
            document_store=_doc_store(),
            arc_store=arc_store,
            consolidated_store=consol,
        )
        checks = await service.global_health_checks()

    assert checks["git_backend"] is True
    assert checks["consolidated_store"] is False
