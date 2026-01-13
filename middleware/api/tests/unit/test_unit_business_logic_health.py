from unittest.mock import MagicMock, patch
import sys

from middleware.api.arc_store import ArcStore
from middleware.api.business_logic import BusinessLogic


def test_check_health_success() -> None:
    """Test check_health when all services are healthy."""
    store = MagicMock(spec=ArcStore)
    store.check_health.return_value = True
    logic = BusinessLogic(store)

    # Setup mocks
    mock_redis_module = MagicMock()
    mock_redis_client = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis_client
    mock_redis_client.ping.return_value = True
    
    mock_celery_module = MagicMock()
    mock_celery_module.BACKEND_URL = "redis://mock"
    mock_celery_app = MagicMock()
    mock_conn = MagicMock()
    mock_celery_app.connection_or_acquire.return_value.__enter__.return_value = mock_conn
    mock_celery_module.celery_app = mock_celery_app

    # Patch sys.modules to intercept imports
    with patch.dict(sys.modules, {
        "redis": mock_redis_module, 
        "middleware.api.celery_app": mock_celery_module
    }):
        result = logic.check_health()

        expected = {
            "backend_reachable": True,
            "redis_reachable": True,
            "rabbitmq_reachable": True,
        }
        assert result == expected
        store.check_health.assert_called_once()
    

def test_check_health_partial_failure() -> None:
    """Test check_health when some services fail."""
    store = MagicMock(spec=ArcStore)
    store.check_health.return_value = False  # Backend fails
    logic = BusinessLogic(store)

    # Setup mocks
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.side_effect = Exception("Redis down")
    
    mock_celery_module = MagicMock()
    mock_celery_module.BACKEND_URL = "redis://mock"
    mock_celery_app = MagicMock()
    # Connection fails
    mock_conn = MagicMock()
    mock_conn.ensure_connection.side_effect = Exception("RabbitMQ down")
    mock_celery_app.connection_or_acquire.return_value.__enter__.return_value = mock_conn
    mock_celery_module.celery_app = mock_celery_app

    with patch.dict(sys.modules, {
        "redis": mock_redis_module, 
        "middleware.api.celery_app": mock_celery_module
    }):
        result = logic.check_health()
        
        expected = {
            "backend_reachable": False,
            "redis_reachable": False,
            "rabbitmq_reachable": False,
        }
        assert result == expected
