#!/usr/bin/env python3
"""Health check script for Celery worker and its dependencies.

This module provides functionality to verify the health of:
- ArcStore backend (Git repository or GitLab API)
- CouchDB (ARC and Harvest storage)
- RabbitMQ (Celery message broker)
"""

import logging
import os
import sys
from http import HTTPStatus
from pathlib import Path

import aiohttp

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.git_repo import GitRepo
from middleware.api.arc_store.gitlab_api import GitlabApi
from middleware.api.config import Config
from middleware.api.worker.celery_app import celery_app

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("worker_health")


async def check_worker_health() -> bool:
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
        if config.git_repo:
            store = GitRepo(config.git_repo)
        elif config.gitlab_api:
            store = GitlabApi(config.gitlab_api)
        else:
            logger.error("Invalid ArcStore configuration")
            return False

        # Check backend (Git/GitLab) - These are synchronous
        backend_reachable = False
        try:
            backend_reachable = store.check_health()
        except (ConnectionError, TimeoutError) as e:
            logger.error("Backend health check failed: %s", e)

        # Check CouchDB (doc store)
        couchdb_reachable = False
        try:
            # We use a simple HTTP GET to avoid complex database setup during health check
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session, session.get(config.couchdb.url) as resp:
                couchdb_reachable = resp.status == HTTPStatus.OK
        except Exception as e:  # noqa: BLE001
            logger.error("CouchDB health check failed: %s", e)

        # Check RabbitMQ (broker)
        rabbitmq_reachable = False
        try:
            with celery_app.connection_or_acquire() as conn:
                conn.ensure_connection(max_retries=1)
                rabbitmq_reachable = True
        except Exception as e:  # noqa: BLE001
            logger.error("RabbitMQ health check failed: %s", e)

        health_status = {
            "backend_reachable": backend_reachable,
            "couchdb_reachable": couchdb_reachable,
            "rabbitmq_reachable": rabbitmq_reachable,
        }

        logger.info("Health status: %s", health_status)

        # Return True only if ALL checks pass
        if not all(health_status.values()):
            logger.error("Some health checks failed")
            return False

        return True

    except Exception as e:  # noqa: BLE001
        logger.error("Health check exception: %s", e)
        return False


if __name__ == "__main__":
    import asyncio

    if asyncio.run(check_worker_health()):
        sys.exit(0)
    else:
        sys.exit(1)
