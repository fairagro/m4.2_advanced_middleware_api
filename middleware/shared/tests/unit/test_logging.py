"""Tests for logging configuration module."""

import logging
from unittest.mock import MagicMock, patch

from middleware.shared.config.logging import configure_logging


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_logging_with_existing_handlers(self) -> None:
        """Test configure_logging with existing handlers."""
        # Setup
        root_logger = logging.getLogger()
        mock_handler = MagicMock()
        root_logger.handlers = [mock_handler]
        original_level = root_logger.level

        try:
            # Execute
            configure_logging("DEBUG")

            # Assert - logging converts strings to level ints
            mock_handler.setLevel.assert_called_with("DEBUG")
            assert root_logger.level == logging.DEBUG
        finally:
            root_logger.level = original_level
            root_logger.handlers = []

    def test_configure_logging_with_multiple_handlers(self) -> None:
        """Test configure_logging with multiple existing handlers."""
        # Setup
        root_logger = logging.getLogger()
        mock_handler1 = MagicMock()
        mock_handler2 = MagicMock()
        root_logger.handlers = [mock_handler1, mock_handler2]
        original_level = root_logger.level

        try:
            # Execute
            configure_logging("INFO")

            # Assert
            mock_handler1.setLevel.assert_called_with("INFO")
            mock_handler2.setLevel.assert_called_with("INFO")
            assert root_logger.level == logging.INFO
        finally:
            root_logger.level = original_level
            root_logger.handlers = []

    def test_configure_logging_without_existing_handlers(self) -> None:
        """Test configure_logging when no handlers exist."""
        # Setup
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        root_logger.handlers = []

        try:
            # Execute
            with patch("logging.basicConfig") as mock_basic_config:
                configure_logging("WARNING")

                # Assert
                mock_basic_config.assert_called_once_with(level="WARNING")
        finally:
            root_logger.handlers = original_handlers

    def test_configure_logging_different_levels(self) -> None:
        """Test configure_logging with different log levels."""
        # Setup
        root_logger = logging.getLogger()
        mock_handler = MagicMock()
        root_logger.handlers = [mock_handler]
        original_level = root_logger.level

        try:
            # Test each log level
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            for level_str, level_int in level_map.items():
                configure_logging(level_str)  # type: ignore[arg-type]
                mock_handler.setLevel.assert_called_with(level_str)
                assert root_logger.level == level_int
        finally:
            root_logger.level = original_level
            root_logger.handlers = []
