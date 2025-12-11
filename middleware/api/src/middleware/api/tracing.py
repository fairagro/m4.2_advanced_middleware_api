"""
OpenTelemetry tracing configuration for the middleware API.

This module initializes and configures OpenTelemetry for distributed tracing,
with support for FastAPI auto-instrumentation, console logging, and OTLP export to Signoz.
"""

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult

if TYPE_CHECKING:
    from fastapi import FastAPI

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
    service_name: str = "middleware-api", otlp_endpoint: str | None = None
) -> tuple[TracerProvider, trace.Tracer]:
    """
    Initialize OpenTelemetry tracing with console and optional OTLP exporter.

    Args:
        service_name: The service name for traces (default: "middleware-api")
        otlp_endpoint: Optional OTLP endpoint URL (e.g. http://signoz:4318)

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

    # Always add console exporter for development/debugging
    console_exporter = SimpleConsoleSpanExporter()
    tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))

    # Optionally add OTLP exporter for Signoz/Jaeger/etc
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OpenTelemetry OTLP exporter configured: %s", otlp_endpoint)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to configure OTLP exporter: %s", e)

    # Set the global tracer provider
    trace.set_tracer_provider(tracer_provider)

    # Get a tracer for this module
    tracer = trace.get_tracer(__name__)

    logger.info(
        "OpenTelemetry tracing initialized (console=%s, otlp=%s)",
        True,
        otlp_endpoint is not None,
    )

    return tracer_provider, tracer


def instrument_fastapi(app: "FastAPI", tracer_provider: TracerProvider | None = None) -> None:
    """
    Instrument a FastAPI application with OpenTelemetry.

    This enables automatic tracing of HTTP requests and responses.

    Args:
        app: The FastAPI application instance
        tracer_provider: Optional custom TracerProvider (uses global if not provided)
    """
    try:
        # Instrument FastAPI for automatic HTTP span creation
        FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)

        # Also instrument requests library for any outbound HTTP calls
        RequestsInstrumentor().instrument(tracer_provider=tracer_provider)

        logger.info("FastAPI and requests instrumentation enabled")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to instrument FastAPI: %s", exc)


def get_tracer(name: str = __name__) -> trace.Tracer:
    """
    Get a tracer instance with the given name.

    Args:
        name: The tracer name (typically __name__)

    Returns:
        A Tracer instance
    """
    return trace.get_tracer(name)
