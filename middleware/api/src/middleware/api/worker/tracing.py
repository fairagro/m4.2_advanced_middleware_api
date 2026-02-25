"""Tracing instrumentation for the Celery worker."""

import logging
from typing import TYPE_CHECKING, NamedTuple

from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace import TracerProvider

from middleware.shared.tracing import initialize_logging, initialize_tracing

if TYPE_CHECKING:
    from celery import Celery

    from ..config import Config

logger = logging.getLogger(__name__)


class WorkerTracingResult(NamedTuple):
    """Result of setting up worker OpenTelemetry instrumentation."""

    tracer_provider: TracerProvider
    logger_provider: LoggerProvider


def setup_worker_tracing(app: "Celery", config: "Config") -> WorkerTracingResult:
    """Set up tracing and logging for the Celery worker.

    Args:
        app: The Celery application instance.
        config: The application configuration.

    Returns:
        WorkerTracingResult with tracer_provider and logger_provider.
    """
    otlp_endpoint = str(config.otel.endpoint) if config.otel.endpoint else None

    # Initialize tracing
    tracer_provider, _ = initialize_tracing(
        service_name="middleware-worker",
        otlp_endpoint=otlp_endpoint,
        log_console_spans=config.otel.log_console_spans,
    )

    # Initialize logging
    logger_provider = initialize_logging(
        service_name="middleware-worker",
        otlp_endpoint=otlp_endpoint,
        log_level=getattr(logging, config.log_level),
        otlp_log_level=getattr(logging, config.otel.log_level),
    )

    # Instrument Celery
    CeleryInstrumentor().instrument(app=app)

    # Instrument external dependencies (used within tasks)
    RequestsInstrumentor().instrument()

    logger.info("Celery worker instrumented for OpenTelemetry (with Requests)")

    return WorkerTracingResult(tracer_provider=tracer_provider, logger_provider=logger_provider)
