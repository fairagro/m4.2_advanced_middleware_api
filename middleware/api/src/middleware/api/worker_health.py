#!/usr/bin/env python3
"""Health check script for Celery worker and its dependencies.

This module provides functionality to verify the health of:
- ArcStore backend (Git repository or GitLab API)
- Redis (Celery result backend)
- RabbitMQ (Celery message broker)
"""

import logging
import os
import sys
from pathlib import Path

import redis

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.git_repo import GitRepo
from middleware.api.arc_store.gitlab_api import GitlabApi
from middleware.api.celery_app import celery_app
from middleware.api.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("worker_health")


def check_worker_health() -> bool:
    """Check health of the worker and its dependencies."""
    try:
        # Load config
        config_file = Path(os.environ.get("MIDDLEWARE_API_CONFIG", "/run/secrets/middleware-api-config"))
        if not config_file.is_file():
            logger.error("Config file not found: %s", config_file)
            return False

        config = Config.from_yaml_file(config_file)

        # Initialize ArcStore
        store: ArcStore
        if config.gitlab_api:
            store = GitlabApi(config.gitlab_api)
        elif config.git_repo:
            store = GitRepo(config.git_repo)
        else:
            logger.error("Invalid ArcStore configuration")
            return False

        # Check backend (Git/GitLab)
        backend_reachable = False
        try:
            backend_reachable = store.check_health()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Backend health check failed: %s", e)

        # Check Redis (result backend)
        redis_reachable = False
        try:
            redis_url = config.celery.result_backend if config.celery else "redis://localhost:6379/0"
            r = redis.from_url(redis_url)
            r.ping()
            redis_reachable = True
        except redis.RedisError as e:
            logger.error("Redis health check failed: %s", e)

        # Check RabbitMQ (broker)
        rabbitmq_reachable = False
        try:
            with celery_app.connection_or_acquire() as conn:
                conn.ensure_connection(max_retries=1)
                rabbitmq_reachable = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("RabbitMQ health check failed: %s", e)

        health_status = {
            "backend_reachable": backend_reachable,
            "redis_reachable": redis_reachable,
            "rabbitmq_reachable": rabbitmq_reachable,
        }

        logger.info("Health status: %s", health_status)

        # Return True only if ALL checks pass
        if not all(health_status.values()):
            logger.error("Some health checks failed")
            return False

        return True

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Health check exception: %s", e)
        return False


if __name__ == "__main__":
    if check_worker_health():
        sys.exit(0)
    else:
        sys.exit(1)
