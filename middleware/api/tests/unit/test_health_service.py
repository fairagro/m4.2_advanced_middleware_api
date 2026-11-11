"""Unit tests for ApiHealthService dependency checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.health_service import ApiHealthService


def _doc_store() -> MagicMock:
    store = MagicMock()
    store.health_check = AsyncMock(return_value=True)
    return store


def _arc_store(*, healthy: bool = True) -> MagicMock:
    store = MagicMock()
    store.check_health = MagicMock(return_value=healthy)
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
        arc_store=_arc_store(),
    )
    checks = await service.readiness_checks()

    assert checks["couchdb_reachable"] is False
    doc_store.health_check.assert_awaited_once()


@pytest.mark.asyncio
async def test_git_backends_use_injected_arc_store() -> None:
    """Git-backend check uses the injected ArcStore (no transient construction)."""
    arc_store = _arc_store(healthy=True)
    config = MagicMock()
    config.consolidated_store = None
    config.health_checks.global_health_check_workers = False
    config.health_checks.global_health_check_git_backend = True
    config.health_checks.readiness_check_couchdb = False
    config.health_checks.readiness_check_rabbitmq = False

    with patch("middleware.api.health_service.asyncio.to_thread", new=AsyncMock(return_value=True)):
        service = ApiHealthService(
            config,
            MagicMock(),
            MagicMock(),
            document_store=_doc_store(),
            arc_store=arc_store,
        )
        checks = await service.global_health_checks()

    assert checks["git_backend"] is True
    assert "consolidated_store" not in checks


@pytest.mark.asyncio
async def test_git_backends_mark_false_when_check_raises() -> None:
    """Git-backend failures surface as False without constructing transient stores."""
    arc_store = _arc_store()
    config = MagicMock()
    config.consolidated_store = MagicMock()

    with patch(
        "middleware.api.health_service.asyncio.to_thread",
        new=AsyncMock(side_effect=RuntimeError("unreachable")),
    ):
        service = ApiHealthService(
            config,
            MagicMock(),
            MagicMock(),
            document_store=_doc_store(),
            arc_store=arc_store,
        )
        results = await service._check_git_backends()

    assert results == {"git_backend": False, "consolidated_store": False}


@pytest.mark.asyncio
async def test_git_backends_include_consolidated_when_configured() -> None:
    """Both slots appear in health when consolidated_store is wired."""
    arc_store = _arc_store(healthy=True)
    consol = _arc_store(healthy=False)
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
