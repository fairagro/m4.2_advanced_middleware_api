"""Tests for error handling during API setup/lifespan."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from middleware.api.api import Api
from middleware.api.business_logic import SetupError

@pytest.mark.asyncio
async def test_lifespan_setup_error_reraised() -> None:
    """Test that SetupError during lifespan setup is re-raised."""
    
    # Mock config
    mock_config = AsyncMock()
    mock_config.log_level = "DEBUG"
    mock_config.otel.endpoint = None
    mock_config.otel.log_console_spans = False
    mock_config.otel.log_level = "DEBUG"
    mock_config.celery.broker_url = "memory://"
    mock_config.celery.result_backend = "cache+memory://"
    mock_config.known_rdis = []
    
    with patch("middleware.api.api.Config"), \
         patch("middleware.api.api.BusinessLogicFactory.create") as mock_factory, \
         patch("middleware.api.api.initialize_tracing", return_value=(AsyncMock(), AsyncMock())), \
         patch("middleware.api.api.initialize_logging"), \
         patch("middleware.api.api.instrument_app"), \
         patch("middleware.api.api.loaded_config", mock_config):
        
        # Setup mock business logic that fails
        mock_bl = AsyncMock()
        mock_bl.setup.side_effect = SetupError("Setup failed intentionally")
        mock_factory.return_value = mock_bl
        
        api_instance = Api(mock_config)
        app = api_instance.app
        
        # We need to manually trigger the lifespan to test it
        # FastAPI lifespan is complex to trigger manually in units without TestClient
        # But we can test the internal lifespan function
        
        # lifespan is defined inside __init__, so we have to get it from the app
        lifespan_handler = app.router.lifespan_context
        
        with pytest.raises(SetupError) as excinfo:
            async with lifespan_handler(app):
                pass
        
        assert "Setup failed intentionally" in str(excinfo.value)
        mock_bl.setup.assert_awaited_once()

@pytest.mark.asyncio
async def test_lifespan_generic_exception_reraised() -> None:
    """Test that generic Exception during lifespan setup is re-raised."""
    
    # Mock config
    mock_config = AsyncMock()
    mock_config.log_level = "DEBUG"
    mock_config.otel.endpoint = None
    mock_config.otel.log_console_spans = False
    mock_config.otel.log_level = "DEBUG"
    mock_config.celery.broker_url = "memory://"
    mock_config.celery.result_backend = "cache+memory://"
    
    with patch("middleware.api.api.Config"), \
         patch("middleware.api.api.BusinessLogicFactory.create") as mock_factory, \
         patch("middleware.api.api.initialize_tracing", return_value=(AsyncMock(), AsyncMock())), \
         patch("middleware.api.api.initialize_logging"), \
         patch("middleware.api.api.instrument_app"), \
         patch("middleware.api.api.loaded_config", mock_config):
        
        # Setup mock business logic that fails with generic exception
        mock_bl = AsyncMock()
        mock_bl.setup.side_effect = ValueError("Unexpected error")
        mock_factory.return_value = mock_bl
        
        api_instance = Api(mock_config)
        app = api_instance.app
        
        lifespan_handler = app.router.lifespan_context
        
        with pytest.raises(ValueError) as excinfo:
            async with lifespan_handler(app):
                pass
        
        assert "Unexpected error" in str(excinfo.value)
        mock_bl.setup.assert_awaited_once()
