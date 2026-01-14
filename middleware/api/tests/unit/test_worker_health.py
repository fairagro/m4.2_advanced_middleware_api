
import sys
import unittest.mock
from unittest.mock import MagicMock, patch
import pytest # type: ignore
from middleware.api.worker_health import check_worker_health

def test_check_worker_health_success() -> None:
    """Test worker health check success."""
    mock_bl = MagicMock()
    mock_bl.check_health.return_value = {
        "backend_reachable": True,
        "redis_reachable": True,
        "rabbitmq_reachable": True,
    }
    
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = "/tmp/test"

    with patch("middleware.api.worker_health.Path") as mock_path, \
         patch("middleware.api.worker_health.Config") as mock_config_cls, \
         patch("middleware.api.worker_health.GitRepo") as mock_repo, \
         patch("middleware.api.worker_health.BusinessLogic", return_value=mock_bl):
        
        mock_path.return_value.is_file.return_value = True
        mock_config_cls.from_yaml_file.return_value = mock_config
        
        assert check_worker_health() is True

def test_check_worker_health_failure() -> None:
    """Test worker health check failure."""
    mock_bl = MagicMock()
    mock_bl.check_health.return_value = {
        "backend_reachable": False,
        "redis_reachable": True,
        "rabbitmq_reachable": True,
    }
    
    mock_config = MagicMock()
    mock_config.gitlab_api = None
    mock_config.git_repo = "/tmp/test"
    
    with patch("middleware.api.worker_health.Path") as mock_path, \
         patch("middleware.api.worker_health.Config") as mock_config_cls, \
         patch("middleware.api.worker_health.GitRepo"), \
         patch("middleware.api.worker_health.BusinessLogic", return_value=mock_bl):
        
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
