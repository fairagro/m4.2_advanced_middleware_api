"""SQL-to-ARC middleware component entry point."""

import argparse
import asyncio
import logging
import multiprocessing
import time
from pathlib import Path

from pydantic import ValidationError

from middleware.api_client import ApiClient
from middleware.shared.config.config_wrapper import ConfigWrapper
from middleware.shared.config.logging import configure_logging
from middleware.shared.tracing import initialize_tracing
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.database import Database
from middleware.sql_to_arc.processor import process_investigations
from middleware.sql_to_arc.stats import ProcessingStats

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments, ignoring unknown args (e.g., pytest flags)."""
    parser = argparse.ArgumentParser(description="SQL to ARC Converter")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to configuration file (default: config.yaml)",
    )
    args, _ = parser.parse_known_args()
    return args


async def run_conversion(config: Config) -> ProcessingStats:
    """Run the conversion."""
    db = Database(config.connection_string.get_secret_value())
    async with ApiClient(config.api_client) as client:
        return await process_investigations(db, client, config)


async def main() -> None:
    """Execute the main entry point."""
    args = parse_args()
    try:
        wrapper = ConfigWrapper.from_yaml_file(args.config, prefix="SQL_TO_ARC")
        config = Config.from_config_wrapper(wrapper)
        configure_logging(config.log_level)
    except (FileNotFoundError, IsADirectoryError, ValidationError) as e:
        logger.error("Failed to load configuration: %s", e)
        return

    otlp_endpoint = str(config.otel.endpoint) if config.otel.endpoint else None
    _tracer_provider, tracer = initialize_tracing(
        service_name="sql_to_arc",
        otlp_endpoint=otlp_endpoint,
        log_console_spans=config.otel.log_console_spans,
    )

    with tracer.start_as_current_span("sql_to_arc.main"):
        logger.info("Starting SQL-to-ARC conversion with config: %s", args.config)
        try:
            start_time = time.perf_counter()
            stats = await run_conversion(config)
            end_time = time.perf_counter()
            stats.duration_seconds = end_time - start_time

            logger.info("SQL-to-ARC conversion completed. Report:")
            print(stats.to_jsonld(rdi_identifier=config.rdi, rdi_url=config.rdi_url))

            if stats.failed_datasets > 0:
                logger.warning(
                    "Conversion finished with %d failures out of %d datasets.",
                    stats.failed_datasets,
                    stats.found_datasets,
                )
            else:
                logger.info("Conversion finished successfully. %d datasets processed.", stats.found_datasets)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.critical("Fatal error during conversion process: %s", e, exc_info=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    asyncio.run(main())
