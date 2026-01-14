#!/usr/bin/env python3
import sys
import logging
import os
from pathlib import Path

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.git_repo import GitRepo
from middleware.api.arc_store.gitlab_api import GitlabApi
from middleware.api.business_logic import BusinessLogic
from middleware.api.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("worker_health")

def check_worker_health() -> bool:
    """Check health of the worker and its dependencies."""
    try:
        # Load config to initialize BusinessLogic
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

        # Initialize BusinessLogic
        bl = BusinessLogic(store)
        
        # Run health check
        # This checks backend (Git/GitLab), Redis, and RabbitMQ
        health_status = bl.check_health()
        
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
