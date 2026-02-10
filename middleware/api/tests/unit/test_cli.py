"""Unit tests for the CLI module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from pydantic import ValidationError

from middleware.api.business_logic import SetupError
from middleware.api.cli import setup_couchdb


@pytest.mark.asyncio
async def test_setup_couchdb_config_not_found() -> None:
    """Test setup_couchdb when configuration file is not found."""
    with (
        patch("middleware.api.cli.Path.is_file", return_value=False),
        patch("middleware.api.cli.logger") as mock_logger,
        pytest.raises(SystemExit) as exc_info,
    ):
        await setup_couchdb()

    assert exc_info.value.code == 1
    mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_setup_couchdb_yaml_error() -> None:
    """Test setup_couchdb when configuration file is malformed."""
    with (
        patch("middleware.api.cli.Path.is_file", return_value=True),
        patch("middleware.api.cli.Config.from_yaml_file", side_effect=yaml.YAMLError("Malformed YAML")),
        patch("middleware.api.cli.logger") as mock_logger,
        pytest.raises(SystemExit) as exc_info,
    ):
        await setup_couchdb()

    assert exc_info.value.code == 1
    # Check that the error was logged with "Configuration error"
    assert any("Configuration error" in str(call) for call in mock_logger.error.call_args_list)


@pytest.mark.asyncio
async def test_setup_couchdb_validation_error() -> None:
    """Test setup_couchdb when configuration is invalid."""
    # Create a simple ValidationError
    validation_error = ValidationError.from_exception_data("Config", [])

    with (
        patch("middleware.api.cli.Path.is_file", return_value=True),
        patch("middleware.api.cli.Config.from_yaml_file", side_effect=validation_error),
        patch("middleware.api.cli.logger") as mock_logger,
        pytest.raises(SystemExit) as exc_info,
    ):
        await setup_couchdb()

    assert exc_info.value.code == 1
    assert any("Configuration error" in str(call) for call in mock_logger.error.call_args_list)


@pytest.mark.asyncio
async def test_setup_couchdb_setup_error() -> None:
    """Test setup_couchdb when business logic setup fails."""
    mock_config = MagicMock()
    mock_bl = MagicMock()
    # Make setup an async mock that raises SetupError
    mock_bl.setup = AsyncMock(side_effect=SetupError("Setup failed"))
    mock_bl.close = AsyncMock()

    with (
        patch("middleware.api.cli.Path.is_file", return_value=True),
        patch("middleware.api.cli.Config.from_yaml_file", return_value=mock_config),
        patch("middleware.api.cli.BusinessLogicFactory.create", return_value=mock_bl),
        patch("middleware.api.cli.logger") as mock_logger,
        pytest.raises(SystemExit) as exc_info,
    ):
        await setup_couchdb()

    assert exc_info.value.code == 1
    assert any("Setup failed" in str(call) for call in mock_logger.error.call_args_list)
    mock_bl.close.assert_called_once()


@pytest.mark.asyncio
async def test_setup_couchdb_runtime_error() -> None:
    """Test setup_couchdb when a RuntimeError occurs."""
    with (
        patch("middleware.api.cli.Path.is_file", return_value=True),
        patch("middleware.api.cli.Config.from_yaml_file", side_effect=RuntimeError("Runtime error")),
        patch("middleware.api.cli.logger") as mock_logger,
        pytest.raises(SystemExit) as exc_info,
    ):
        await setup_couchdb()

    assert exc_info.value.code == 1
    assert any("Runtime error" in str(call) for call in mock_logger.error.call_args_list)


@pytest.mark.asyncio
async def test_setup_couchdb_success() -> None:
    """Test setup_couchdb successful execution."""
    mock_config = MagicMock()
    mock_bl = MagicMock()
    # Make setup and close async mocks
    mock_bl.setup = AsyncMock(return_value=None)
    mock_bl.close = AsyncMock()

    with (
        patch("middleware.api.cli.Path.is_file", return_value=True),
        patch("middleware.api.cli.Config.from_yaml_file", return_value=mock_config),
        patch("middleware.api.cli.BusinessLogicFactory.create", return_value=mock_bl),
        patch("middleware.api.cli.logger") as mock_logger,
    ):
        await setup_couchdb()
        # Verify setup was called
        mock_bl.setup.assert_called_once()
        # Verify close was called
        mock_bl.close.assert_called_once()
        # Verify success message was logged
        assert any("completed successfully" in str(call) for call in mock_logger.info.call_args_list)
