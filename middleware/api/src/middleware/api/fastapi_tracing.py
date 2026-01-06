"""FastAPI specific tracing instrumentation."""

import logging
from typing import TYPE_CHECKING

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

if TYPE_CHECKING:
    from fastapi import FastAPI


logger = logging.getLogger(__name__)


def instrument_fastapi(app: "FastAPI") -> None:
    """Instrument a FastAPI application with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()
    logger.info("FastAPI app instrumented for OpenTelemetry")
