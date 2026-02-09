"""CLI tool for CouchDB setup."""

import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from middleware.api.business_logic import SetupError
from middleware.api.business_logic_factory import BusinessLogicFactory
from middleware.api.config import Config

logger = logging.getLogger("middleware_api.cli")


async def setup_couchdb() -> None:
    """Initialize CouchDB system databases."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config_path = Path(os.environ.get("MIDDLEWARE_API_CONFIG", "/run/secrets/middleware-api-config"))
    if not config_path.is_file():
        logger.error("Configuration file not found at %s", config_path)
        sys.exit(1)

    try:
        config = Config.from_yaml_file(config_path)
        # Create BusinessLogic in Processor mode to access setup()
        business_logic = BusinessLogicFactory.create(config, mode="worker")

        logger.info("Starting CouchDB setup...")
        await business_logic.setup()
        logger.info("CouchDB setup completed successfully.")
    except (yaml.YAMLError, ValidationError) as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except SetupError as e:
        logger.error("Setup failed: %s", e)
        sys.exit(1)
    except RuntimeError as e:
        logger.error("Runtime error: %s", e)
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-exception-caught # noqa: BLE001
        logger.error("An unexpected error occurred: %s", e, exc_info=True)
        sys.exit(1)


def main() -> None:
    """Run the main entry point for the CLI."""
    asyncio.run(setup_couchdb())


if __name__ == "__main__":
    main()
