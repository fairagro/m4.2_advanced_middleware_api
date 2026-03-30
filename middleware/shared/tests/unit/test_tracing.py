"""Unit tests for middleware.shared.tracing."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace.export import SpanExportResult

from middleware.shared.tracing import (
    SimpleConsoleSpanExporter,
    initialize_logging,
    initialize_tracing,
)

# ---------------------------------------------------------------------------
# SimpleConsoleSpanExporter
# ---------------------------------------------------------------------------


def _make_span(
    name: str = "test-span",
    start_time: int | None = 1_000_000,
    end_time: int | None = 2_000_000,
    attributes: dict | None = None,
) -> MagicMock:
    span = MagicMock()
    span.name = name
    span.start_time = start_time
    span.end_time = end_time
    span.attributes = attributes
    return span


def test_simple_console_exporter_exports_span() -> None:
    """Export a span with timing info and no attributes."""
    exporter = SimpleConsoleSpanExporter()
    span = _make_span()
    result = exporter.export([span])

    assert result == SpanExportResult.SUCCESS


def test_simple_console_exporter_no_timing() -> None:
    """Export a span where start_time or end_time is None (duration = 0)."""
    exporter = SimpleConsoleSpanExporter()
    span = _make_span(start_time=None, end_time=None)
    result = exporter.export([span])

    assert result == SpanExportResult.SUCCESS


def test_simple_console_exporter_with_attributes() -> None:
    """Export a span that has attributes."""
    exporter = SimpleConsoleSpanExporter()
    span = _make_span(attributes={"key": "value"})
    exporter.export([span])


def test_simple_console_exporter_empty_spans() -> None:
    """Exporting an empty list is a no-op and returns SUCCESS."""
    exporter = SimpleConsoleSpanExporter()

    assert exporter.export([]) == SpanExportResult.SUCCESS


def test_simple_console_exporter_shutdown() -> None:
    """shutdown() should not raise."""
    SimpleConsoleSpanExporter().shutdown()


def test_simple_console_exporter_force_flush() -> None:
    """force_flush() should return True."""
    assert SimpleConsoleSpanExporter().force_flush() is True


# ---------------------------------------------------------------------------
# initialize_tracing
# ---------------------------------------------------------------------------


def test_initialize_tracing_defaults() -> None:
    """initialize_tracing with default args returns provider and tracer."""
    provider, tracer = initialize_tracing()
    assert provider is not None
    assert tracer is not None


def test_initialize_tracing_no_console() -> None:
    """initialize_tracing without console exporter does not add console processor."""
    provider, tracer = initialize_tracing(log_console_spans=False)
    assert provider is not None


def test_initialize_tracing_with_otlp() -> None:
    """initialize_tracing with valid OTLP endpoint adds OTLP processor."""
    with patch("middleware.shared.tracing.OTLPSpanExporter"):
        provider, tracer = initialize_tracing(
            service_name="test-svc",
            otlp_endpoint="http://localhost:4318",
            log_console_spans=False,
        )
    assert provider is not None


def test_initialize_tracing_otlp_failure(caplog: pytest.LogCaptureFixture) -> None:
    """initialize_tracing logs a warning when OTLP exporter raises."""
    with (
        patch(
            "middleware.shared.tracing.OTLPSpanExporter",
            side_effect=ValueError("bad endpoint"),
        ),
        caplog.at_level(logging.WARNING, logger="middleware.shared.tracing"),
    ):
        provider, _ = initialize_tracing(
            otlp_endpoint="http://bad-host:4318",
            log_console_spans=False,
        )
    assert provider is not None
    assert any("Failed to configure OTLP exporter" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# initialize_logging
# ---------------------------------------------------------------------------


def test_initialize_logging_no_endpoint() -> None:
    """initialize_logging without endpoint returns a LoggerProvider."""
    provider = initialize_logging()

    assert isinstance(provider, LoggerProvider)


def test_initialize_logging_with_otlp_endpoint() -> None:
    """initialize_logging with OTLP endpoint configures exporters."""
    with patch("middleware.shared.tracing.OTLPLogExporter"):
        provider = initialize_logging(
            service_name="test-svc",
            otlp_endpoint="http://localhost:4318",
            log_console=False,
        )

    assert isinstance(provider, LoggerProvider)


def test_initialize_logging_with_console_exporter() -> None:
    """initialize_logging with console exporter enabled."""
    with patch("middleware.shared.tracing.OTLPLogExporter"):
        provider = initialize_logging(
            otlp_endpoint="http://localhost:4318",
            log_console=True,
        )

    assert isinstance(provider, LoggerProvider)
