"""Logging configuration module.

This module provides functionality to configure logging levels for all handlers
and the root logger across the application, and installs URL-userinfo redaction
so oauth2/Git credentials do not appear in formatted log output.
"""

from __future__ import annotations

import logging

from middleware.shared.config.config_base import LogLevel
from middleware.shared.security.url_redact import redact_url_userinfo

_HANDLER_REDACT_ATTR = "_fairagro_url_userinfo_redact"


class RedactingFormatter(logging.Formatter):
    """Wrap another formatter and redact URL userinfo in the final log line."""

    def __init__(self, wrapped: logging.Formatter | None = None) -> None:
        """Initialize with an optional underlying formatter."""
        super().__init__()
        self._wrapped = wrapped if wrapped is not None else logging.Formatter()

    def format(self, record: logging.LogRecord) -> str:
        """Format the record, then strip URL credentials from the result."""
        return redact_url_userinfo(self._wrapped.format(record))


class _RedactingLogFilter(logging.Filter):
    """Scrub URL userinfo from record message/args before handlers format."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: PLR6301
        """Redact ``record.msg`` / string ``args`` in place."""
        if isinstance(record.msg, str):
            record.msg = redact_url_userinfo(record.msg)
        if isinstance(record.args, dict):
            record.args = {
                key: redact_url_userinfo(value) if isinstance(value, str) else value
                for key, value in record.args.items()
            }
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_url_userinfo(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True


def install_url_userinfo_redaction(logger: logging.Logger | None = None) -> None:
    """Ensure handlers redact ``https://userinfo@`` in every formatted log line.

    Safe to call repeatedly; already-wrapped handlers are skipped. Also attaches a
    logger-level filter so late log records still get message/args scrubbed when
    possible.
    """
    target = logging.getLogger() if logger is None else logger
    if not any(isinstance(f, _RedactingLogFilter) for f in target.filters):
        target.addFilter(_RedactingLogFilter())
    for handler in target.handlers:
        if getattr(handler, _HANDLER_REDACT_ATTR, False):
            continue
        if not any(isinstance(f, _RedactingLogFilter) for f in handler.filters):
            handler.addFilter(_RedactingLogFilter())
        current = handler.formatter
        if isinstance(current, RedactingFormatter):
            setattr(handler, _HANDLER_REDACT_ATTR, True)
            continue
        handler.setFormatter(RedactingFormatter(current))
        setattr(handler, _HANDLER_REDACT_ATTR, True)


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
    install_url_userinfo_redaction(root)
