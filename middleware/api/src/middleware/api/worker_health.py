#!/usr/bin/env python3
"""Health check script for Celery worker chart-internal dependencies.

This readiness check only verifies services managed by the same Helm chart:
- RabbitMQ (always for celery-worker deployment)
- CouchDB (only if enabled in the chart)
"""

import asyncio
import logging
import os
import socket
import sys
from http import HTTPStatus
from urllib.parse import urlparse

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("worker_health")


async def _check_rabbitmq(host: str, port: int) -> bool:
    """Check RabbitMQ TCP reachability."""

    def _probe() -> bool:
        with socket.create_connection((host, port), timeout=5):
            return True

    try:
        return await asyncio.to_thread(_probe)
    except OSError as e:
        logger.error("RabbitMQ health check failed: %s", e)
        return False


async def _check_couchdb(url: str) -> bool:
    """Check CouchDB HTTP reachability."""
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session, session.get(url) as resp:
            return resp.status == HTTPStatus.OK
    except Exception as e:  # noqa: BLE001
        logger.error("CouchDB health check failed: %s", e)
        return False


def _parse_broker_endpoint(broker_url: str) -> tuple[str, int] | None:
    """Extract RabbitMQ host and port from CELERY_BROKER_URL."""
    try:
        parsed = urlparse(broker_url)
        host = parsed.hostname
        port = parsed.port or 5672
    except ValueError:
        return None

    if not host:
        return None

    return host, port


async def check_worker_health() -> bool:
    """Check health of chart-internal dependencies required by celery-worker."""
    try:
        broker_url = os.environ.get("CELERY_BROKER_URL", "").strip()
        if not broker_url:
            logger.error("CELERY_BROKER_URL must be set")
            return False

        broker_endpoint = _parse_broker_endpoint(broker_url)
        if broker_endpoint is None:
            logger.error("Invalid CELERY_BROKER_URL: %s", broker_url)
            return False

        rabbitmq_host, rabbitmq_port = broker_endpoint

        rabbitmq_reachable = await _check_rabbitmq(rabbitmq_host, rabbitmq_port)

        chart_couchdb_enabled = os.environ.get("CHART_COUCHDB_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        couchdb_reachable = True
        couchdb_url = os.environ.get("COUCHDB_URL", "").strip()
        if chart_couchdb_enabled:
            if not couchdb_url:
                logger.error("COUCHDB_URL must be set when CHART_COUCHDB_ENABLED=true")
                return False
            couchdb_reachable = await _check_couchdb(couchdb_url)

        health_status = {
            "rabbitmq_host": rabbitmq_host,
            "rabbitmq_port": rabbitmq_port,
            "chart_couchdb_enabled": chart_couchdb_enabled,
            "couchdb_reachable": couchdb_reachable,
            "rabbitmq_reachable": rabbitmq_reachable,
        }

        logger.info("Health status: %s", health_status)

        if not (rabbitmq_reachable and couchdb_reachable):
            logger.error("Some health checks failed")
            return False

        return True

    except Exception as e:  # noqa: BLE001
        logger.error("Health check exception: %s", e)
        return False


if __name__ == "__main__":
    if asyncio.run(check_worker_health()):
        sys.exit(0)
    else:
        sys.exit(1)
