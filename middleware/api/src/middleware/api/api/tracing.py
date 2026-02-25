"""Tracing instrumentation for the FastAPI application."""

import logging
from typing import TYPE_CHECKING, NamedTuple

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace import TracerProvider

from middleware.shared.tracing import initialize_logging, initialize_tracing

if TYPE_CHECKING:
    from fastapi import FastAPI

    from ..config import Config

logger = logging.getLogger(__name__)


class ApiTracingResult(NamedTuple):
    """Result of setting up API OpenTelemetry instrumentation."""

    tracer_provider: TracerProvider
    logger_provider: LoggerProvider


def setup_api_tracing(app: "FastAPI", config: "Config") -> ApiTracingResult:
    """Set up tracing and logging for the FastAPI application.

    Args:
        app: The FastAPI application instance.
        config: The application configuration.

    Returns:
        ApiTracingResult with tracer_provider and logger_provider.
    """
    otlp_endpoint = str(config.otel.endpoint) if config.otel.endpoint else None

    # Initialize tracing
    tracer_provider, _ = initialize_tracing(
        service_name="middleware-api",
        otlp_endpoint=otlp_endpoint,
        log_console_spans=config.otel.log_console_spans,
    )

    # Initialize logging
    logger_provider = initialize_logging(
        service_name="middleware-api",
        otlp_endpoint=otlp_endpoint,
        log_level=getattr(logging, config.log_level),
        otlp_log_level=getattr(logging, config.otel.log_level),
    )

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument external dependencies
    RequestsInstrumentor().instrument()

    logger.info("FastAPI app instrumented for OpenTelemetry (with Requests)")

    return ApiTracingResult(tracer_provider=tracer_provider, logger_provider=logger_provider)
