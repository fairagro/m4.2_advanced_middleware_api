"""Logging configuration module.

This module provides functionality to configure logging levels for all handlers
and the root logger across the application.
"""

import logging

from middleware.shared.config.config_base import LogLevel


def configure_logging(level: LogLevel) -> None:
    """Configure logging level for all handlers.

    Args:
        level: Logging level to set for all handlers and root logger.
    """
    root = logging.getLogger()
    if root.handlers:
        # vorhandene Handler neu konfigurieren
        for h in root.handlers:
            h.setLevel(level)
        root.setLevel(level)
    else:
        logging.basicConfig(level=level)
