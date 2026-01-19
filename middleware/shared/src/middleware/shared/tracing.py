"""
OpenTelemetry tracing configuration for the middleware API.

This module initializes and configures OpenTelemetry for distributed tracing,
with support for FastAPI auto-instrumentation, console logging, and OTLP export to Signoz.
"""

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http.log_exporter import OTLPLogExporter
from opentelemetry.sdk.logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.logs.export import (
    BatchLogRecordProcessor,
    ConsoleLogRecordExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SimpleConsoleSpanExporter(SpanExporter):
    """Simple span exporter that logs to console."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to console."""
        for span in spans:
            if span.end_time is not None and span.start_time is not None:
                duration_ms = (span.end_time - span.start_time) / 1e6
            else:
                duration_ms = 0.0
            logger.info(
                "SPAN: %s (duration=%0.3fms)",
                span.name,
                duration_ms,
            )
            if span.attributes:
                logger.info("  Attributes: %s", span.attributes)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        """Flush any pending spans."""
        return True


def initialize_tracing(
    service_name: str = "middleware-api",
    otlp_endpoint: str | None = None,
    log_console_spans: bool = True,
) -> tuple[TracerProvider, trace.Tracer]:
    """
    Initialize OpenTelemetry tracing with console and optional OTLP exporter.

    Args:
        service_name: The service name for traces (default: "middleware-api")
        otlp_endpoint: Optional OTLP endpoint URL (e.g. http://signoz:4318)
        log_console_spans: Whether to log spans to console (default: True)

    Returns:
        Tuple of (TracerProvider, Tracer) for use in the application
    """
    # Create a resource describing this service
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.0.0",
        }
    )

    # Create a tracer provider
    tracer_provider = TracerProvider(resource=resource)

    # Optionally add console exporter for development/debugging
    if log_console_spans:
        console_exporter = SimpleConsoleSpanExporter()
        tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))

    # Optionally add OTLP exporter for Signoz/Jaeger/etc
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OpenTelemetry OTLP exporter configured: %s", otlp_endpoint)
        except (ValueError, OSError) as e:
            logger.warning("Failed to configure OTLP exporter: %s", e)

    # Set the global tracer provider
    trace.set_tracer_provider(tracer_provider)

    # Get a tracer for this module
    tracer = trace.get_tracer(__name__)

    logger.info(
        "OpenTelemetry tracing initialized (console=%s, otlp=%s)",
        log_console_spans,
        bool(otlp_endpoint),
    )

    return tracer_provider, tracer


def initialize_logging(
    service_name: str = "middleware-api",
    otlp_endpoint: str | None = None,
    log_console: bool = False,
) -> LoggerProvider:
    """
    Initialize OpenTelemetry logging with optional OTLP exporter.

    Args:
        service_name: The service name for log records.
        otlp_endpoint: Optional OTLP endpoint URL (e.g. http://signoz:4318).
        log_console: Whether to also export logs to console via OTLP SDK exporter.
    """
    resource = Resource.create({"service.name": service_name, "service.version": "0.0.0"})
    logger_provider = LoggerProvider(resource=resource)

    if otlp_endpoint:
        try:
            otlp_log_exporter = OTLPLogExporter(endpoint=f"{otlp_endpoint}/v1/logs")
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
            if log_console:
                logger_provider.add_log_record_processor(BatchLogRecordProcessor(ConsoleLogRecordExporter()))
            set_logger_provider(logger_provider)
            root_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
            logging.getLogger().addHandler(root_handler)
            logger.info("OpenTelemetry log exporter configured: %s", otlp_endpoint)
        except (ValueError, OSError) as e:  # pragma: no cover - defensive path
            logger.warning("Failed to configure OTLP log exporter: %s", e)

    return logger_provider
