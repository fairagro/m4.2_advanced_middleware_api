"""Celery application configuration and initialization.

This module sets up the Celery app for the middleware API, including:
- Broker and backend configuration from YAML config file
- Optional OpenTelemetry instrumentation for distributed tracing
- Task serialization and timezone settings
"""

import logging
import os
import sys
from pathlib import Path

from celery import Celery

from ..config import Config
from .tracing import setup_worker_tracing

logger = logging.getLogger(__name__)

# Load config from YAML file
config_path = Path(os.environ.get("MIDDLEWARE_API_CONFIG", "/run/secrets/middleware-api-config"))

# Global config instance
loaded_config: Config

# Declare celery_app type for mypy
celery_app: Celery

# Check if running in test environment (pytest sets PYTEST_CURRENT_TEST) or if config file doesn't exist
if "pytest" in sys.modules or not config_path.is_file():
    # Create a dummy celery app for testing
    logger.info("Running in test mode - using dummy Celery configuration")
    celery_app = Celery(
        "middleware_api",
        broker="memory://",
        backend="cache+memory://",
        include=[],  # Avoid circular imports in test mode
    )
    # Use a dummy config in test mode to satisfy the non-optional type
    # This also allows the worker to initialize BusinessLogic in tests if needed.
    loaded_config = Config.from_data({
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "memory://"},
        "git_repo": {"url": "http://localhost", "group": "test"},  # nosec
        "require_client_cert": False,
    })
else:
    loaded_config = Config.from_yaml_file(config_path)

    if not loaded_config.celery:
        logger.error("Celery configuration missing in config file")
        raise ValueError("Celery configuration missing in config file")

    broker_url = loaded_config.celery.broker_url.get_secret_value()
    backend_url = loaded_config.celery.result_backend.get_secret_value()

    logger.info("Celery configured with broker: %s", broker_url)

    celery_app = Celery(
        "middleware_api",
        broker=broker_url,
        backend=backend_url,
        include=["middleware.api.worker"],
    )

    setup_worker_tracing(celery_app, loaded_config)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
