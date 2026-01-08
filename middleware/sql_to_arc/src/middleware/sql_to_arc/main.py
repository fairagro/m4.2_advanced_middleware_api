"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import concurrent.futures
import logging
import multiprocessing
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


def build_single_arc_task(
    investigation_row: dict[str, Any],
    studies: list[dict[str, Any]],
    assays_by_study: dict[int, list[dict[str, Any]]],
) -> ArcInvestigation:
    """Build a single ARC investigation object.

    This function is designed to run in a separate process.
    """
    arc = map_investigation(investigation_row)

    for study_row in studies:
        study = map_study(study_row)
        arc.AddRegisteredStudy(study)

        # Add assays for this study
        assays_rows = assays_by_study.get(study_row["id"], [])
        for assay_row in assays_rows:
            assay = map_assay(assay_row)
            study.AddRegisteredAssay(assay)

    return arc


async def fetch_all_investigations(cur: psycopg.AsyncCursor[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch all investigations from the database.

    Args:
        cur: Database cursor.

    Returns:
        List of investigation rows.
    """
    await cur.execute(
        'SELECT id, title, description, submission_time, release_time FROM "ARC_Investigation"',  # LIMIT 10',
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


def build_arc_for_investigation(
    investigation_row: dict[str, Any],
    studies: list[dict[str, Any]],
    assays_by_study: dict[int, list[dict[str, Any]]],
) -> ARC:
    """Build a single ARC for an investigation (CPU-bound operation for ProcessPoolExecutor).

    This function is designed to be called in a separate process.

    Args:
        investigation_row: Investigation database row.
        studies: List of studies for this investigation.
        assays_by_study: Dictionary mapping study_id to list of assays.

    Returns:
        ARC object.
    """
    # Filter assays for these studies
    relevant_assays = {s["id"]: assays_by_study.get(s["id"], []) for s in studies}

    # Build ArcInvestigation
    arc_investigation = build_single_arc_task(investigation_row, studies, relevant_assays)

    # Wrap in ARC container
    return ARC.from_arc_investigation(arc_investigation)


async def process_worker_investigations(
    client: ApiClient,
    investigations: list[dict[str, Any]],
    rdi: str,
    studies_by_investigation: dict[int, list[dict[str, Any]]],
    assays_by_study: dict[int, list[dict[str, Any]]],
    batch_size: int,
    worker_id: int,
    total_workers: int,
    executor: concurrent.futures.ProcessPoolExecutor,
) -> None:
    """Process a list of investigations assigned to this worker.

    Each worker builds ARCs in parallel using ProcessPoolExecutor and uploads them in batches.

    Args:
        client: API client instance.
        investigations: List of investigation rows assigned to this worker.
        rdi: RDI identifier for the ARC upload.
        studies_by_investigation: Pre-fetched studies data.
        assays_by_study: Pre-fetched assays data.
        batch_size: Number of ARCs to upload per batch.
        worker_id: ID of this worker (for logging).
        total_workers: Total number of workers (for logging).
        executor: ProcessPoolExecutor for CPU-bound ARC building.
    """
    if not investigations:
        return

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        "process_worker", attributes={"worker_id": worker_id, "investigation_count": len(investigations), "rdi": rdi}
    ):
        logger.info(
            "Worker %d/%d processing %d investigations...",
            worker_id,
            total_workers,
            len(investigations),
        )

        # Split investigations into batches
        batches: list[list[dict[str, Any]]] = []
        current_batch: list[dict[str, Any]] = []

        for row in investigations:
            current_batch.append(row)
            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []

        # Add remaining batch
        if current_batch:
            batches.append(current_batch)

        logger.info("Worker %d/%d: Processing %d batches", worker_id, total_workers, len(batches))

        # Process each batch sequentially within this worker
        for batch_idx, batch in enumerate(batches):
            batch_info = f"Worker {worker_id}/{total_workers}, Batch {batch_idx + 1}/{len(batches)}"

            with tracer.start_as_current_span(
                "build_batch", attributes={"batch_size": len(batch), "worker_id": worker_id, "batch_idx": batch_idx}
            ):
                logger.info("%s: Building %d ARCs in parallel...", batch_info, len(batch))

                # Build ARCs in parallel using ProcessPoolExecutor (multi-core)
                loop = asyncio.get_event_loop()
                arc_build_futures = []

                for row in batch:
                    inv_id = row["id"]
                    studies = studies_by_investigation.get(inv_id, [])

                    # Submit to ProcessPoolExecutor
                    future = loop.run_in_executor(
                        executor,
                        build_arc_for_investigation,
                        row,
                        studies,
                        assays_by_study,
                    )
                    arc_build_futures.append(future)

                # Wait for all ARC builds to complete
                arc_objects = await asyncio.gather(*arc_build_futures)

            # Upload batch
            try:
                with tracer.start_as_current_span(
                    "upload_batch", attributes={"count": len(arc_objects), "rdi": rdi, "worker_id": worker_id}
                ):
                    response = await client.create_or_update_arcs(
                        rdi=rdi,
                        arcs=arc_objects,
                    )
                logger.info("%s: Upload successful. Created/Updated: %d", batch_info, len(response.arcs))
            except (psycopg.Error, ConnectionError, TimeoutError) as e:
                logger.error("%s: Failed to upload due to connection issue: %s", batch_info, e, exc_info=True)
            except ApiClientError as e:
                logger.error("%s: Failed to upload due to API error: %s", batch_info, e, exc_info=True)


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

        # Step 4: Distribute investigations evenly across workers
        num_workers = config.max_concurrent_arc_builds
        total_investigations = len(investigation_rows)

        logger.info(
            "Distributing %d investigations across %d workers (batch_size=%d)",
            total_investigations,
            num_workers,
            config.batch_size,
        )

        # Split investigations into chunks for each worker
        worker_assignments: list[list[dict[str, Any]]] = [[] for _ in range(num_workers)]
        for idx, investigation in enumerate(investigation_rows):
            worker_id = idx % num_workers
            worker_assignments[worker_id].append(investigation)

        # Log distribution
        for worker_id, assigned_investigations in enumerate(worker_assignments):
            logger.info("Worker %d assigned %d investigations", worker_id + 1, len(assigned_investigations))

        # Process workers concurrently with ProcessPoolExecutor for CPU-bound ARC building
        # Each worker processes its assigned investigations in batches, building ARCs in parallel.
        # Use "spawn" context to avoid deadlocks/warnings in multi-threaded environments (e.g. pytest).
        mp_context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers, mp_context=mp_context) as executor:
            tasks = [
                process_worker_investigations(
                    client,
                    assigned_investigations,
                    config.rdi,
                    studies_by_investigation,
                    assays_by_study,
                    config.batch_size,
                    worker_id=worker_id + 1,
                    total_workers=num_workers,
                    executor=executor,
                )
                for worker_id, assigned_investigations in enumerate(worker_assignments)
                if assigned_investigations  # Skip empty workers
            ]

            await asyncio.gather(*tasks)


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
