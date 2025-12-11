"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]
from opentelemetry import trace
from psycopg.rows import dict_row
from pydantic import ValidationError

from middleware.api_client import ApiClient, ApiClientError
from middleware.shared.config.config_wrapper import ConfigWrapper
from middleware.shared.config.logging import configure_logging
from middleware.shared.tracing import initialize_tracing
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
        'SELECT id, title, description, submission_time, release_time FROM "ARC_Investigation" LIMIT 10',
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


async def process_batch(
    client: ApiClient,
    batch: list[dict[str, Any]],
    rdi: str,
    studies_by_investigation: dict[int, list[dict[str, Any]]],
    assays_by_study: dict[int, list[dict[str, Any]]],
    max_concurrent_builds: int,
    batch_num: int | None = None,
    total_batches: int | None = None,
) -> None:
    """Send a batch of ARCs to the API.

    Builds ARC objects concurrently before uploading.

    Args:
        client: API client instance.
        batch: List of investigation rows (dicts) to build ARCs from.
        rdi: RDI identifier for the ARC upload.
        studies_by_investigation: Pre-fetched studies data.
        assays_by_study: Pre-fetched assays data.
        max_concurrent_builds: Maximum concurrent ARC builds within this batch.
        batch_num: Current batch number (for logging).
        total_batches: Total number of batches (for logging).
    """
    if not batch:
        return

    tracer = trace.get_tracer(__name__)
    batch_info = f"{batch_num}/{total_batches}" if batch_num and total_batches else "unknown"

    with tracer.start_as_current_span(
        "process_batch", attributes={"batch_size": len(batch), "rdi": rdi, "batch_info": batch_info}
    ):
        logger.info(
            "Building batch %s with %d investigations (max concurrent: %d)...",
            batch_info,
            len(batch),
            max_concurrent_builds,
        )

        # Build ArcInvestigation objects concurrently with semaphore
        semaphore = asyncio.Semaphore(max_concurrent_builds)

        async def build_arc(investigation_row: dict[str, Any]) -> ArcInvestigation:
            async with semaphore:
                arc = map_investigation(investigation_row)
                populate_investigation_studies_and_assays(
                    arc,
                    investigation_row["id"],
                    studies_by_investigation,
                    assays_by_study,
                )
                return arc

        with tracer.start_as_current_span("arc.build_investigations", attributes={"count": len(batch)}):
            arc_investigations = await asyncio.gather(*[build_arc(row) for row in batch])

        # Wrap built ArcInvestigation objects in ARC containers
        with tracer.start_as_current_span("arc.wrap_investigations", attributes={"count": len(arc_investigations)}):
            arc_objects = [ARC.from_arc_investigation(inv) for inv in arc_investigations]

        try:
            with tracer.start_as_current_span(
                "api_client.create_or_update_arcs", attributes={"count": len(arc_objects), "rdi": rdi}
            ):
                response = await client.create_or_update_arcs(
                    rdi=rdi,
                    arcs=arc_objects,
                )
            logger.info("Batch %s upload successful. Created/Updated: %d", batch_info, len(response.arcs))
        except (psycopg.Error, ConnectionError, TimeoutError) as e:
            logger.error("Failed to upload batch %s due to connection issue: %s", batch_info, e, exc_info=True)
        except ApiClientError as e:
            logger.error("Failed to upload batch %s due to API error: %s", batch_info, e, exc_info=True)


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

    ARCs within each batch are built concurrently (up to max_concurrent_arc_builds),
    then uploaded together via a single API call.

    Args:
        cur: Database cursor.
        client: API client instance.
        config: Configuration object.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("process_investigations"):
        # Step 1: Fetch all investigations
        logger.info("Fetching all investigations...")
        with tracer.start_as_current_span("db.fetch_investigations"):
            investigation_rows = await fetch_all_investigations(cur)
        logger.info("Found %d investigations", len(investigation_rows))

        if not investigation_rows:
            logger.info("No investigations found, nothing to process")
            return

        # Step 2: Fetch all studies for these investigations in bulk
        investigation_ids = [row["id"] for row in investigation_rows]
        logger.info("Fetching studies for %d investigations...", len(investigation_ids))
        with tracer.start_as_current_span(
            "db.fetch_studies", attributes={"investigation_count": len(investigation_ids)}
        ):
            studies_by_investigation = await fetch_studies_bulk(cur, investigation_ids)
        total_studies = sum(len(studies) for studies in studies_by_investigation.values())
        logger.info("Found %d studies", total_studies)

        # Step 3: Fetch all assays for these studies in bulk
        study_ids = [study["id"] for studies in studies_by_investigation.values() for study in studies]
        logger.info("Fetching assays for %d studies...", len(study_ids))
        with tracer.start_as_current_span("db.fetch_assays", attributes={"study_count": len(study_ids)}):
            assays_by_study = await fetch_assays_bulk(cur, study_ids)
        total_assays = sum(len(assays) for assays in assays_by_study.values())
        logger.info("Found %d assays", total_assays)

        # Step 4: Assemble into batches and process each batch
        batches: list[list[dict[str, Any]]] = []
        current_batch: list[dict[str, Any]] = []

        with tracer.start_as_current_span("assemble_batches"):
            for row in investigation_rows:
                current_batch.append(row)

                # Start new batch if full
                if len(current_batch) >= config.batch_size:
                    batches.append(current_batch)
                    current_batch = []

            # Add remaining batch
            if current_batch:
                batches.append(current_batch)

        logger.info(
            "Assembled %d batches (batch_size=%d, max_concurrent_builds=%d)",
            len(batches),
            config.batch_size,
            config.max_concurrent_arc_builds,
        )

        # Process batches sequentially, each with concurrent ARC builds
        for i, batch in enumerate(batches):
            await process_batch(
                client,
                batch,
                config.rdi,
                studies_by_investigation,
                assays_by_study,
                config.max_concurrent_arc_builds,
                batch_num=i + 1,
                total_batches=len(batches),
            )


async def run_conversion(config: Config) -> None:
    """Run the SQL-to-ARC conversion with the given configuration.

    Args:
        config: Configuration object.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("run_conversion"):
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

    # Initialize OpenTelemetry tracing
    otlp_endpoint = str(config.otel_endpoint) if config.otel_endpoint else None
    _tracer_provider, tracer = initialize_tracing(
        service_name="sql_to_arc",
        otlp_endpoint=otlp_endpoint,
        log_console_spans=config.otel_log_console_spans,
    )

    with tracer.start_as_current_span("sql_to_arc.main"):
        logger.info("Starting SQL-to-ARC conversion with config: %s", args.config)
        await run_conversion(config)
        logger.info("SQL-to-ARC conversion completed.")


if __name__ == "__main__":
    asyncio.run(main())
