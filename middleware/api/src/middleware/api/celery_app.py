import os
from celery import Celery

# Get configuration from environment variables (set by docker-compose)
BROKER_URL = os.environ.get("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
BACKEND_URL = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "middleware_api",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["middleware.api.worker"],
)

# Instrument the Celery app if OTLP endpoint is configured
# Note: In a real deployment, we might want to check the config file or env var explicitly
# For now, we rely on standard OTEL env vars or assume instrumentation is safe to always apply
# The actual export will only happen if a processor/exporter is configured via env vars
try:
    from .tracing import instrument_celery
    instrument_celery(celery_app)
except ImportError:
    # Graceful fallback if dependencies are missing or during build
    pass

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
