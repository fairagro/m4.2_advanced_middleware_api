"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any

import psycopg
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]
from psycopg.rows import dict_row
from pydantic import ValidationError

from middleware.api_client import ApiClient, ApiClientError
from middleware.shared.config.config_wrapper import ConfigWrapper
from middleware.shared.config.logging import configure_logging
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.mapper import map_assay, map_investigation, map_study

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


async def fetch_assays(cur: psycopg.AsyncCursor[dict[str, Any]], study_id: int) -> list[dict[str, Any]]:
    """Fetch assays for a given study."""
    await cur.execute(
        'SELECT id, study_id, measurement_type, technology_type FROM "ARC_Assay" WHERE study_id = %s',
        (study_id,),
    )
    return await cur.fetchall()


async def fetch_studies(cur: psycopg.AsyncCursor[dict[str, Any]], investigation_id: int) -> list[dict[str, Any]]:
    """Fetch studies for a given investigation."""
    await cur.execute(
        "SELECT id, investigation_id, title, description, submission_time, release_time "
        'FROM "ARC_Study" WHERE investigation_id = %s',
        (investigation_id,),
    )
    return await cur.fetchall()


async def process_batch(client: ApiClient, batch: list[ArcInvestigation], rdi: str) -> None:
    """Send a batch of ARCs to the API.

    Args:
        client: API client instance.
        batch: List of ArcInvestigation objects.
        rdi: RDI identifier for the ARC upload.
    """
    if not batch:
        return

    logger.info("Uploading batch of %d ARCs...", len(batch))

    # Wrap ArcInvestigation objects in ARC containers
    arc_objects = [ARC.from_arc_investigation(inv) for inv in batch]

    # Log ROCrate JSON for debugging
    for idx, arc in enumerate(arc_objects):
        rocrate_json = arc.ToROCrateJsonString()
        logger.debug("ARC %d ROCrate JSON: %s", idx, rocrate_json)

    try:
        response = await client.create_or_update_arcs(
            rdi=rdi,
            arcs=arc_objects,
        )
        logger.info("Batch upload successful. Created/Updated: %d", len(response.arcs))
    except (psycopg.Error, ConnectionError, TimeoutError) as e:
        logger.error("Failed to upload batch due to connection issue: %s", e, exc_info=True)
    except ApiClientError as e:
        logger.error("Failed to upload batch due to API error: %s", e, exc_info=True)


async def populate_investigation_studies_and_assays(
    cur: psycopg.AsyncCursor[dict[str, Any]],
    arc: ArcInvestigation,
    investigation_id: int,
) -> None:
    """Populate an investigation with its studies and assays.

    Args:
        cur: Database cursor.
        arc: ArcInvestigation object to populate.
        investigation_id: Investigation ID.
    """
    studies_rows = await fetch_studies(cur, investigation_id)
    for study_row in studies_rows:
        study = map_study(study_row)
        arc.AddRegisteredStudy(study)

        # Fetch and add assays for this study
        assays_rows = await fetch_assays(cur, study_row["id"])
        for assay_row in assays_rows:
            assay = map_assay(assay_row)
            study.AddRegisteredAssay(assay)


async def process_investigations(
    cur: psycopg.AsyncCursor[dict[str, Any]],
    client: ApiClient,
    config: Config,
) -> None:
    """Fetch investigations from DB and process them in batches.

    Args:
        cur: Database cursor.
        client: API client instance.
        config: Configuration object.
    """
    await cur.execute(
        'SELECT id, title, description, submission_time, release_time FROM "ARC_Investigation"',
    )

    batch: list[ArcInvestigation] = []

    async for row in cur:
        arc = map_investigation(row)
        await populate_investigation_studies_and_assays(cur, arc, row["id"])

        batch.append(arc)

        # Process batch if full
        if len(batch) >= config.batch_size:
            await process_batch(client, batch, config.rdi)
            batch = []

    # Process remaining
    if batch:
        await process_batch(client, batch, config.rdi)


async def run_conversion(config: Config) -> None:
    """Run the SQL-to-ARC conversion with the given configuration.

    Args:
        config: Configuration object.
    """
    async with (
        ApiClient(config.api_client) as client,
        await psycopg.AsyncConnection.connect(
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password.get_secret_value(),
            host=config.db_host,
            port=config.db_port,
        ) as conn,
        conn.cursor(row_factory=dict_row) as cur,
    ):
        await process_investigations(cur, client, config)


async def main() -> None:
    """Connect to DB, process investigations, and upload ARCs."""
    args = parse_args()
    try:
        # Load config via ConfigWrapper so ENV/Secrets with prefix 'SQL_TO_ARC' are respected
        wrapper = ConfigWrapper.from_yaml_file(args.config, prefix="SQL_TO_ARC")
        config = Config.from_config_wrapper(wrapper)
        configure_logging(config.log_level)
    except (FileNotFoundError, ValidationError) as e:
        logger.error("Failed to load configuration: %s", e)
        return

    logger.info("Starting SQL-to-ARC conversion with config: %s", args.config)
    await run_conversion(config)
    logger.info("SQL-to-ARC conversion completed.")


if __name__ == "__main__":
    asyncio.run(main())
