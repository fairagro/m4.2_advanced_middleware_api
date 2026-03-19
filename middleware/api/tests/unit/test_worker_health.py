"""Unit tests for worker health check."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.worker_health import check_worker_health


def setup_aiohttp_mock(status: int = 200, side_effect: Exception | None = None) -> MagicMock:
    """Set up aiohttp mock."""
    mock_response = AsyncMock()
    mock_response.status = status

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    if side_effect:
        mock_session.get.side_effect = side_effect
    else:
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock()
        mock_session.get.return_value = mock_get_ctx

    return mock_session


@pytest.mark.asyncio
async def test_check_worker_health_success_with_couchdb() -> None:
    """Health check passes when chart-internal RabbitMQ and CouchDB are reachable."""
    mock_session = setup_aiohttp_mock(status=200)

    with (
        patch("middleware.api.worker_health.socket.create_connection") as mock_conn,
        patch("middleware.api.worker_health.aiohttp.ClientSession", return_value=mock_session),
        patch.dict(
            "os.environ",
            {
                "CELERY_BROKER_URL": "amqp://user:pass@my-rabbit:5672//",
                "CHART_COUCHDB_ENABLED": "true",
                "COUCHDB_URL": "http://my-couch:5984",
            },
            clear=False,
        ),
    ):
        mock_conn.return_value.__enter__.return_value = None
        mock_conn.return_value.__exit__.return_value = None

        assert await check_worker_health() is True


@pytest.mark.asyncio
async def test_check_worker_health_success_without_couchdb() -> None:
    """Health check passes when only RabbitMQ is managed by the chart."""
    with (
        patch("middleware.api.worker_health.socket.create_connection") as mock_conn,
        patch.dict(
            "os.environ",
            {
                "CELERY_BROKER_URL": "amqp://user:pass@my-rabbit:5672//",
                "CHART_COUCHDB_ENABLED": "false",
            },
            clear=True,
        ),
    ):
        mock_conn.return_value.__enter__.return_value = None
        mock_conn.return_value.__exit__.return_value = None

        assert await check_worker_health() is True


@pytest.mark.asyncio
async def test_check_worker_health_rabbitmq_failure() -> None:
    """Health check fails when RabbitMQ is unreachable."""
    with (
        patch(
            "middleware.api.worker_health.socket.create_connection",
            side_effect=OSError("RabbitMQ connection failed"),
        ),
        patch.dict(
            "os.environ",
            {
                "CELERY_BROKER_URL": "amqp://user:pass@my-rabbit:5672//",
                "CHART_COUCHDB_ENABLED": "false",
            },
            clear=True,
        ),
    ):
        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_couchdb_failure() -> None:
    """Health check fails when chart-managed CouchDB is unreachable."""
    mock_session = setup_aiohttp_mock(side_effect=Exception("CouchDB connection failed"))

    with (
        patch("middleware.api.worker_health.socket.create_connection") as mock_conn,
        patch("middleware.api.worker_health.aiohttp.ClientSession", return_value=mock_session),
        patch.dict(
            "os.environ",
            {
                "CELERY_BROKER_URL": "amqp://user:pass@my-rabbit:5672//",
                "CHART_COUCHDB_ENABLED": "true",
                "COUCHDB_URL": "http://my-couch:5984",
            },
            clear=True,
        ),
    ):
        mock_conn.return_value.__enter__.return_value = None
        mock_conn.return_value.__exit__.return_value = None

        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_missing_rabbitmq_env() -> None:
    """Health check fails if required broker URL is missing."""
    with patch.dict("os.environ", {}, clear=True):
        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_invalid_broker_url() -> None:
    """Health check fails if broker URL has an invalid port."""
    with patch.dict(
        "os.environ",
        {
            "CELERY_BROKER_URL": "amqp://user:pass@my-rabbit:not-a-number//",
        },
        clear=True,
    ):
        assert await check_worker_health() is False
