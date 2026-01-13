from unittest.mock import MagicMock, patch
from typing import Any

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from middleware.api.worker import process_arc, MiddlewareTask
import middleware.api.worker
from middleware.shared.api_models.models import CreateOrUpdateArcsResponse, ArcResponse, ArcStatus

def test_process_arc_success() -> None:
    """Test successful task execution."""
    
    # Mock business logic result
    mock_result = CreateOrUpdateArcsResponse(
        rdi="test-rdi",
        client_id="test-client",
        message="ok",
        arcs=[
             ArcResponse(
                id="arc-1",
                status=ArcStatus.CREATED,
                timestamp="2024-01-01T00:00:00Z"
             )
        ]
    )
    
    # We need to mock the MiddlewareTask._business_logic class attribute
    # Since we are calling the function via .apply(), the base class __call__ is invoked.
    
    with patch.object(MiddlewareTask, "_business_logic", new=MagicMock()) as mock_bl:
        # Define the async return value
        async def async_return(*args: Any, **kwargs: Any) -> CreateOrUpdateArcsResponse:
            return mock_result
            
        mock_bl.create_or_update_arcs.side_effect = async_return
        
        # We also need to mock the request context of the task
        with patch("celery.app.task.Task.request") as mock_request:
            mock_request.id = "test-task-id"
            
            # Since process_arc creates a new event loop, we need to ensure it doesn't conflict
            # or simply let it run if it's isolated.
            # However, if we are in an environment that already has a loop (like pytest-asyncio might set up),
            # creating a new one might be tricky. But process_arc is synchronous, so it should be fine.
            
            result = process_arc.apply(args=("test-rdi", {"dummy": "data"}, "test-client")).get()
            
            # Verify result dictionary structure
            assert result["rdi"] == "test-rdi"
            assert result["client_id"] == "test-client"
            assert result["message"] == "ok"
            assert len(result["arcs"]) == 1


def test_process_arc_initialization() -> None:
    """Test that the worker initializes business logic."""
    
    # We need to simulate the environment where MiddlewareTask._business_logic is None
    # and verify MiddlewareTask initializes it.
    
    # This is hard to test in isolation without resetting the class attribute state
    # or using a subprocess.
    pass


def test_process_arc_failure() -> None:
    """Test task failure handling."""
    
    with patch.object(MiddlewareTask, "_business_logic", new=MagicMock()) as mock_bl:
        # Define the async return value that raises an exception
        async def async_raise(*args: Any, **kwargs: Any) -> None:
            raise ValueError("Processing failed")
            
        mock_bl.create_or_update_arcs.side_effect = async_raise
        
        with patch("celery.app.task.Task.request") as mock_request:
            mock_request.id = "test-task-id-fail"
            
            with pytest.raises(ValueError, match="Processing failed"):
                process_arc.apply(args=("test-rdi", {"dummy": "data"}, "test-client")).get()


def test_middleware_task_initialization() -> None:
    """Test that MiddlewareTask initializes business logic."""
    
    # Create a mock task instance
    task = MiddlewareTask()
    
    # Mock Config, BusinessLogic, Path, and Store classes
    with patch("middleware.api.worker.Config") as mock_config_cls, \
         patch("middleware.api.worker.BusinessLogic") as mock_bl_cls, \
         patch("middleware.api.worker.Path") as mock_path_cls, \
         patch("middleware.api.worker.GitlabApi") as mock_gitlab_cls, \
         patch("middleware.api.worker.GitRepo") as mock_gitrepo_cls, \
         patch.object(task, "run", return_value="result") as mock_run:
         
        # Setup Path mock to return True for is_file()
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = True
        mock_path_cls.return_value = mock_path_instance
        
        # Setup Mock Config to return a value for gitlab_api
        mock_config_instance = MagicMock()
        # Ensure gitlab_api is truthy to trigger that branch, or set git_repo
        mock_config_instance.gitlab_api = {"some": "config"}
        mock_config_instance.git_repo = None
        mock_config_cls.from_yaml_file.return_value = mock_config_instance

        # Ensure MiddlewareTask._business_logic is None
        with patch.object(MiddlewareTask, "_business_logic", None):
            
            # Execute __call__
            task(1, 2, key="value")
            
            # Verify BusinessLogic was initialized
            mock_config_cls.from_yaml_file.assert_called_once()
            mock_gitlab_cls.assert_called_once_with({"some": "config"})
            mock_bl_cls.assert_called_once()
            
            # Verify run was called
            mock_run.assert_called_with(1, 2, key="value")


def test_middleware_task_config_missing() -> None:
    """Test that MiddlewareTask raises RuntimeError if config file is missing."""
    
    task = MiddlewareTask()
    
    with patch.object(MiddlewareTask, "_business_logic", None), \
         patch("middleware.api.worker.Path") as mock_path_cls:
        
        # Setup Path mock to return False for is_file()
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = False
        mock_path_cls.return_value = mock_path_instance
        
        with pytest.raises(RuntimeError, match="Config file not found"):
            task()


def test_middleware_task_invalid_store_config() -> None:
    """Test that MiddlewareTask raises ValueError if store config is invalid."""
    
    task = MiddlewareTask()
    
    with patch.object(MiddlewareTask, "_business_logic", None), \
         patch("middleware.api.worker.Path") as mock_path_cls, \
         patch("middleware.api.worker.Config") as mock_config_cls:
        
        # Setup Path mock to return True
        mock_path_instance = MagicMock()
        mock_path_instance.is_file.return_value = True
        mock_path_cls.return_value = mock_path_instance
        
        # Setup Config to satisfy neither gitlab nor git_repo
        mock_config_instance = MagicMock()
        mock_config_instance.gitlab_api = None
        mock_config_instance.git_repo = None
        mock_config_cls.from_yaml_file.return_value = mock_config_instance
        
        with pytest.raises(ValueError, match="Invalid ArcStore configuration"):
            task()

