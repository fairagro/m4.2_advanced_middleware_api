"""OpenTelemetry tracing instrumentation."""

import logging
from typing import TYPE_CHECKING, Any

from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor

if TYPE_CHECKING:
    from celery import Celery
    from fastapi import FastAPI


logger = logging.getLogger(__name__)


def instrument_app(app: "FastAPI") -> None:
    """Instrument a FastAPI application with OpenTelemetry.
    
    This includes:
    - FastAPI instrumentation (which builds on Starlette)
    - Starlette instrumentation directly (for extra coverage)
    - Redis instrumentation
    - Requests instrumentation
    """
    # Instrument FastAPI (handles HTTP requests)
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrument Starlette (provides underlying ASGI support)
    StarletteInstrumentor().instrument()
    
    # Instrument external dependencies
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    
    logger.info("FastAPI app instrumented for OpenTelemetry (with Redis, Requests)")


def instrument_celery(app: "Celery", **kwargs: Any) -> None:
    """Instrument a Celery application with OpenTelemetry."""
    CeleryInstrumentor().instrument(**kwargs)
    
    # Also instrument dependencies that might be used within tasks
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    
    logger.info("Celery app instrumented for OpenTelemetry")
