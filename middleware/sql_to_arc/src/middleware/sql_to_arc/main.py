"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import logging
from collections import defaultdict
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


async def fetch_all_investigations(cur: psycopg.AsyncCursor[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch all investigations from the database.

    Args:
        cur: Database cursor.

    Returns:
        List of investigation rows.
    """
    await cur.execute(
        'SELECT id, title, description, submission_time, release_time FROM "ARC_Investigation"',
    )
    return await cur.fetchall()


async def fetch_studies_bulk(
    cur: psycopg.AsyncCursor[dict[str, Any]], investigation_ids: list[int]
) -> dict[int, list[dict[str, Any]]]:
    """Fetch all studies for given investigation IDs in a single query.

    Args:
        cur: Database cursor.
        investigation_ids: List of investigation IDs.

    Returns:
        Dictionary mapping investigation_id to list of study rows.
    """
    if not investigation_ids:
        return {}

    await cur.execute(
        "SELECT id, investigation_id, title, description, submission_time, release_time "
        'FROM "ARC_Study" WHERE investigation_id = ANY(%s)',
        (investigation_ids,),
    )
    rows = await cur.fetchall()

    # Group studies by investigation_id
    studies_by_investigation: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        studies_by_investigation[row["investigation_id"]].append(row)

    return studies_by_investigation


async def fetch_assays_bulk(
    cur: psycopg.AsyncCursor[dict[str, Any]], study_ids: list[int]
) -> dict[int, list[dict[str, Any]]]:
    """Fetch all assays for given study IDs in a single query.

    Args:
        cur: Database cursor.
        study_ids: List of study IDs.

    Returns:
        Dictionary mapping study_id to list of assay rows.
    """
    if not study_ids:
        return {}

    await cur.execute(
        'SELECT id, study_id, measurement_type, technology_type FROM "ARC_Assay" WHERE study_id = ANY(%s)',
        (study_ids,),
    )
    rows = await cur.fetchall()

    # Group assays by study_id
    assays_by_study: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        assays_by_study[row["study_id"]].append(row)

    return assays_by_study


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


def populate_investigation_studies_and_assays(
    arc: ArcInvestigation,
    investigation_id: int,
    studies_by_investigation: dict[int, list[dict[str, Any]]],
    assays_by_study: dict[int, list[dict[str, Any]]],
) -> None:
    """Populate an investigation with its studies and assays using pre-fetched data.

    Args:
        arc: ArcInvestigation object to populate.
        investigation_id: Investigation ID.
        studies_by_investigation: Dictionary mapping investigation_id to study rows.
        assays_by_study: Dictionary mapping study_id to assay rows.
    """
    studies_rows = studies_by_investigation.get(investigation_id, [])
    for study_row in studies_rows:
        study = map_study(study_row)
        arc.AddRegisteredStudy(study)

        # Add assays for this study
        assays_rows = assays_by_study.get(study_row["id"], [])
        for assay_row in assays_rows:
            assay = map_assay(assay_row)
            study.AddRegisteredAssay(assay)


async def process_investigations(
    cur: psycopg.AsyncCursor[dict[str, Any]],
    client: ApiClient,
    config: Config,
) -> None:
    """Fetch investigations from DB and process them in batches.

    This function optimizes database access by fetching all data in 3 queries:
    1. Fetch all investigations
    2. Fetch all studies for those investigations
    3. Fetch all assays for those studies

    Then assembles the nested ARC objects in memory, avoiding the N+1 query problem.

    Args:
        cur: Database cursor.
        client: API client instance.
        config: Configuration object.
    """
    # Step 1: Fetch all investigations
    logger.info("Fetching all investigations...")
    investigation_rows = await fetch_all_investigations(cur)
    logger.info("Found %d investigations", len(investigation_rows))

    if not investigation_rows:
        logger.info("No investigations found, nothing to process")
        return

    # Step 2: Fetch all studies for these investigations in bulk
    investigation_ids = [row["id"] for row in investigation_rows]
    logger.info("Fetching studies for %d investigations...", len(investigation_ids))
    studies_by_investigation = await fetch_studies_bulk(cur, investigation_ids)
    total_studies = sum(len(studies) for studies in studies_by_investigation.values())
    logger.info("Found %d studies", total_studies)

    # Step 3: Fetch all assays for these studies in bulk
    study_ids = [study["id"] for studies in studies_by_investigation.values() for study in studies]
    logger.info("Fetching assays for %d studies...", len(study_ids))
    assays_by_study = await fetch_assays_bulk(cur, study_ids)
    total_assays = sum(len(assays) for assays in assays_by_study.values())
    logger.info("Found %d assays", total_assays)

    # Step 4: Assemble ARC objects in memory and process in batches
    batch: list[ArcInvestigation] = []

    for row in investigation_rows:
        arc = map_investigation(row)
        populate_investigation_studies_and_assays(
            arc,
            row["id"],
            studies_by_investigation,
            assays_by_study,
        )

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
    except (FileNotFoundError, IsADirectoryError, ValidationError) as e:
        logger.error("Failed to load configuration: %s", e)
        return

    logger.info("Starting SQL-to-ARC conversion with config: %s", args.config)
    await run_conversion(config)
    logger.info("SQL-to-ARC conversion completed.")


if __name__ == "__main__":
    asyncio.run(main())
