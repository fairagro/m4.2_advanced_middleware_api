"""Unit tests for worker health check."""

from unittest.mock import MagicMock, patch

from middleware.api.worker_health import check_worker_health


def test_check_worker_health_success() -> None:
    """Test worker health check success."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = "/tmp/test"
    mock_config.celery.result_backend = "redis://localhost:6379/0"

    mock_store = MagicMock()
    mock_store.check_health.return_value = True

    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    mock_celery_conn = MagicMock()

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.redis.from_url", return_value=mock_redis),
        patch("middleware.api.worker_health.celery_app.connection_or_acquire") as mock_conn,
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        mock_conn.return_value.__enter__.return_value = mock_celery_conn
        mock_celery_conn.ensure_connection.return_value = None

        assert check_worker_health() is True


def test_check_worker_health_backend_failure() -> None:
    """Test worker health check when backend fails."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = "/tmp/test"
    mock_config.celery.result_backend = "redis://localhost:6379/0"

    mock_store = MagicMock()
    mock_store.check_health.return_value = False  # Backend unreachable

    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    mock_celery_conn = MagicMock()

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.redis.from_url", return_value=mock_redis),
        patch("middleware.api.worker_health.celery_app.connection_or_acquire") as mock_conn,
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        mock_conn.return_value.__enter__.return_value = mock_celery_conn
        mock_celery_conn.ensure_connection.return_value = None

        assert check_worker_health() is False


def test_check_worker_health_redis_failure() -> None:
    """Test worker health check when Redis fails."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = "/tmp/test"
    mock_config.celery.result_backend = "redis://localhost:6379/0"

    mock_store = MagicMock()
    mock_store.check_health.return_value = True

    mock_celery_conn = MagicMock()

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.redis.from_url", side_effect=Exception("Redis connection failed")),
        patch("middleware.api.worker_health.celery_app.connection_or_acquire") as mock_conn,
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        mock_conn.return_value.__enter__.return_value = mock_celery_conn
        mock_celery_conn.ensure_connection.return_value = None

        assert check_worker_health() is False


def test_check_worker_health_rabbitmq_failure() -> None:
    """Test worker health check when RabbitMQ fails."""
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = "/tmp/test"
    mock_config.celery.result_backend = "redis://localhost:6379/0"

    mock_store = MagicMock()
    mock_store.check_health.return_value = True

    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with (
        patch("middleware.api.worker_health.Path") as mock_path,
        patch("middleware.api.worker_health.Config") as mock_config_cls,
        patch("middleware.api.worker_health.GitRepo", return_value=mock_store),
        patch("middleware.api.worker_health.redis.from_url", return_value=mock_redis),
        patch(
            "middleware.api.worker_health.celery_app.connection_or_acquire",
            side_effect=Exception("RabbitMQ connection failed"),
        ),
    ):
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config

        assert check_worker_health() is False


def test_check_worker_health_config_missing() -> None:
    """Test worker health check when config missing."""
    with patch("middleware.api.worker_health.Path") as mock_path:
        mock_path.return_value.is_file.return_value = False
        assert check_worker_health() is False


def test_check_worker_health_exception() -> None:
    """Test worker health check exception handling."""
    with patch("middleware.api.worker_health.Path", side_effect=Exception("Disk error")):
        assert check_worker_health() is False
