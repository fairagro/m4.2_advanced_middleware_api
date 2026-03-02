"""Unit tests for worker health check."""

from pathlib import Path
from types import SimpleNamespace
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
async def test_check_worker_health_success(tmp_path: Path) -> None:
    """Test worker health check success."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = str(tmp_path / "repo")
    mock_config.couchdb = SimpleNamespace(url="http://localhost:5984")

    mock_store = MagicMock()
    mock_store.check_health.return_value = True

    mock_celery_conn = MagicMock()
    mock_session = setup_aiohttp_mock(status=200)

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.aiohttp.ClientSession", return_value=mock_session),
        patch("middleware.api.worker_health.celery_app.connection_or_acquire") as mock_conn,
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        mock_conn.return_value.__enter__.return_value = mock_celery_conn
        mock_celery_conn.ensure_connection.return_value = None

        assert await check_worker_health() is True


@pytest.mark.asyncio
async def test_check_worker_health_backend_failure(tmp_path: Path) -> None:
    """Test worker health check when backend fails."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = str(tmp_path / "repo")
    mock_config.couchdb = SimpleNamespace(url="http://localhost:5984")

    mock_store = MagicMock()
    mock_store.check_health.return_value = False  # Backend unreachable

    mock_celery_conn = MagicMock()
    mock_session = setup_aiohttp_mock(status=200)

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.aiohttp.ClientSession", return_value=mock_session),
        patch("middleware.api.worker_health.celery_app.connection_or_acquire") as mock_conn,
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        mock_conn.return_value.__enter__.return_value = mock_celery_conn
        mock_celery_conn.ensure_connection.return_value = None

        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_couchdb_failure(tmp_path: Path) -> None:
    """Test worker health check when CouchDB fails."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = str(tmp_path / "repo")
    mock_config.couchdb = SimpleNamespace(url="http://localhost:5984")

    mock_store = MagicMock()
    mock_store.check_health.return_value = True

    mock_celery_conn = MagicMock()
    mock_session = setup_aiohttp_mock(side_effect=Exception("CouchDB connection failed"))

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.aiohttp.ClientSession", return_value=mock_session),
        patch("middleware.api.worker_health.celery_app.connection_or_acquire") as mock_conn,
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        mock_conn.return_value.__enter__.return_value = mock_celery_conn
        mock_celery_conn.ensure_connection.return_value = None

        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_rabbitmq_failure(tmp_path: Path) -> None:
    """Test worker health check when RabbitMQ fails."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = str(tmp_path / "repo")
    mock_config.couchdb = SimpleNamespace(url="http://localhost:5984")

    mock_store = MagicMock()
    mock_store.check_health.return_value = True
    mock_session = setup_aiohttp_mock(status=200)

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.aiohttp.ClientSession", return_value=mock_session),
        patch(
            "middleware.api.worker_health.celery_app.connection_or_acquire",
            side_effect=Exception("RabbitMQ connection failed"),
        ),
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config

        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_config_missing() -> None:
    """Test worker health check when config missing."""
    with patch("middleware.api.worker_health.Path") as mock_path:
        mock_path.return_value.is_file.return_value = False
        assert await check_worker_health() is False


@pytest.mark.asyncio
async def test_check_worker_health_exception() -> None:
    """Test worker health check exception handling."""
    with patch("middleware.api.worker_health.Path", side_effect=Exception("Disk error")):
        assert await check_worker_health() is False
