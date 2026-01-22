"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import concurrent.futures
import json
import logging
import multiprocessing
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import psycopg
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]
from opentelemetry import trace
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, ValidationError

from middleware.api_client import ApiClient, ApiClientError
from middleware.shared.config.config_wrapper import ConfigWrapper
from middleware.shared.config.logging import configure_logging
from middleware.shared.tracing import initialize_tracing
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.mapper import map_assay, map_investigation, map_study

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Suppress noisy library logs at INFO level
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class ProcessingStats(BaseModel):
    """Statistics for the conversion process."""

    found_datasets: int = 0
    total_studies: int = 0
    total_assays: int = 0
    failed_datasets: int = 0
    failed_ids: list[str] = []
    duration_seconds: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def merge(self, other: "ProcessingStats") -> None:
        """Merge another stats object into this one."""
        self.found_datasets += other.found_datasets
        self.failed_datasets += other.failed_datasets
        self.failed_ids.extend(other.failed_ids)
        # Note: total_studies, total_assays are counted centrally, not merged from workers

    def to_jsonld(self, rdi_identifier: str | None = None, rdi_url: str | None = None) -> str:
        """Return JSON-LD representation of stats using Schema.org and PROV terms."""
        # Convert duration to ISO 8601 duration format (PTx.xS)
        duration_iso = f"PT{self.duration_seconds:.2f}S"

        ld_struct = {
            "@context": {
                "schema": "http://schema.org/",
                "prov": "http://www.w3.org/ns/prov#",
                "void": "http://rdfs.org/ns/void#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                # Map duration to schema:duration (Expects ISO 8601 string)
                "duration": {"@id": "schema:duration", "@type": "schema:Duration"},
                # Map failed IDs to schema:error (list of strings)
                "failed_ids": {"@id": "schema:error", "@container": "@set"},
                # Map status
                "status": {"@id": "schema:actionStatus"},
                # Use VoID for counts (statistic items)
                "found_datasets": {"@id": "void:entities", "@type": "xsd:integer"},
                # Custom descriptive terms for study/assay counts as they are domain specific
                # We map them to schema:result for semantics, but keep key names
                "total_studies": {"@id": "schema:result", "@type": "xsd:integer"},
                "total_assays": {"@id": "schema:result", "@type": "xsd:integer"},
            },
            "@type": ["prov:Activity", "schema:CreateAction"],
            "schema:name": "SQL to ARC Conversion Run",
            "schema:instrument": {
                "@type": "schema:SoftwareApplication",
                "schema:name": "FAIRagro Middleware SQL-to-ARC",
            },
            # Process status
            "status": "schema:CompletedActionStatus" if self.failed_datasets == 0 else "schema:FailedActionStatus",
            # Metrics
            "duration": duration_iso,
            "duration_seconds": round(self.duration_seconds, 2),  # Keep raw float for easy parsing
            "found_datasets": self.found_datasets,
            "total_studies": self.total_studies,
            "total_assays": self.total_assays,
            "failed_datasets": self.failed_datasets,
            "failed_ids": sorted(self.failed_ids),
        }

        if rdi_identifier and rdi_url:
            ld_struct["prov:used"] = {
                "@id": rdi_url,
                "@type": "schema:Organization",  # RDI acts as an Organization/Service
                "schema:identifier": rdi_identifier,
                "schema:name": f"Research Data Infrastructure: {rdi_identifier}",
            }

        return json.dumps(ld_struct, indent=2)


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


class WorkerContext(BaseModel):
    """Context data for a worker process."""

    client: Any  # ApiClient, but Any to allow mocking
    rdi: str
    studies_by_investigation: dict[int, list[dict[str, Any]]]
    assays_by_study: dict[int, list[dict[str, Any]]]
    batch_size: int
    worker_id: int
    total_workers: int
    executor: Any  # ProcessPoolExecutor is not Pydantic-friendly easily, so Any

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def _upload_and_update_stats(
    ctx: WorkerContext,
    valid_arcs: list[ARC],
    valid_rows: list[dict[str, Any]],
    stats: ProcessingStats,
    batch_info: str,
) -> None:
    """Upload batch of ARCs and update statistics."""
    tracer = trace.get_tracer(__name__)
    try:
        with tracer.start_as_current_span(
            "sql_to_arc.main._upload_and_update_stats",
            attributes={"count": len(valid_arcs), "rdi": ctx.rdi, "worker_id": ctx.worker_id},
        ):
            response = await ctx.client.create_or_update_arcs(
                rdi=ctx.rdi,
                arcs=valid_arcs,
            )
        logger.info("%s: Upload request finished. API reported %d successful ARCs.", batch_info, len(response.arcs))

        if len(response.arcs) < len(valid_arcs):
            logger.warning(
                "%s: Only %d/%d ARCs were successfully processed by API.",
                batch_info,
                len(response.arcs),
                len(valid_arcs),
            )
            # Identify exactly which ARCs failed by comparing sent ARCs with successful response IDs
            successful_ids = {a.id for a in response.arcs}

            for arc in valid_arcs:
                identifier = getattr(arc, "Identifier", None)
                if identifier:
                    # Use identifier directly (no hashing)
                    if identifier not in successful_ids:
                        stats.failed_datasets += 1
                        stats.failed_ids.append(identifier)
                else:
                    logger.error("%s: ARC with missing identifier failed upload", batch_info)
                    stats.failed_datasets += 1
                    stats.failed_ids.append("unknown_id")

    except (psycopg.Error, ConnectionError, TimeoutError, ApiClientError) as e:
        logger.error("%s: Failed to upload batch: %s", batch_info, e, exc_info=True)
        stats.failed_datasets += len(valid_arcs)
        for row in valid_rows:
            stats.failed_ids.append(str(row["id"]))


async def process_batch(  # pylint: disable=too-many-locals
    ctx: WorkerContext,
    batch: list[dict[str, Any]],
    batch_idx: int,
    total_batches: int,
) -> ProcessingStats:
    """Process a single batch of investigations."""
    stats = ProcessingStats()
    tracer = trace.get_tracer(__name__)
    batch_info = f"Worker {ctx.worker_id}/{ctx.total_workers}, Batch {batch_idx + 1}/{total_batches}"

    valid_arcs: list[ARC] = []
    valid_rows: list[dict[str, Any]] = []

    with tracer.start_as_current_span(
        "sql_to_arc.main.process_batch",
        attributes={"batch_size": len(batch), "worker_id": ctx.worker_id, "batch_idx": batch_idx},
    ):
        logger.info("%s: Building %d ARCs in parallel...", batch_info, len(batch))

        # Build ARCs in parallel using ProcessPoolExecutor (multi-core)
        loop = asyncio.get_event_loop()
        arc_build_futures = []

        for row in batch:
            inv_id = row["id"]
            studies = ctx.studies_by_investigation.get(inv_id, [])

            # Submit to ProcessPoolExecutor
            future = loop.run_in_executor(
                ctx.executor,
                build_arc_for_investigation,
                row,
                studies,
                ctx.assays_by_study,
            )
            arc_build_futures.append(future)

        # Wait for all ARC builds to complete, gathering exceptions
        results = await asyncio.gather(*arc_build_futures, return_exceptions=True)

        for i, res in enumerate(results):
            row_id = str(batch[i]["id"])
            if isinstance(res, Exception):
                logger.error("%s: Failed to build ARC for investigation %s: %s", batch_info, row_id, res)
                stats.failed_datasets += 1
                stats.failed_ids.append(row_id)
            elif res is None:
                logger.error("%s: Build returned None for investigation %s", batch_info, row_id)
                stats.failed_datasets += 1
                stats.failed_ids.append(row_id)
            else:
                valid_arcs.append(cast(ARC, res))
                valid_rows.append(batch[i])

    if valid_arcs:
        await _upload_and_update_stats(ctx, valid_arcs, valid_rows, stats, batch_info)

    return stats


async def process_worker_investigations(
    ctx: WorkerContext,
    investigations: list[dict[str, Any]],
) -> ProcessingStats:
    """Process a list of investigations assigned to this worker."""
    stats = ProcessingStats(found_datasets=len(investigations))
    if not investigations:
        return stats

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        "sql_to_arc.main.process_worker_investigations",
        attributes={"worker_id": ctx.worker_id, "investigation_count": len(investigations), "rdi": ctx.rdi},
    ):
        logger.info(
            "Worker %d/%d processing %d investigations...",
            ctx.worker_id,
            ctx.total_workers,
            len(investigations),
        )

        # Split investigations into batches
        batches: list[list[dict[str, Any]]] = []
        current_batch: list[dict[str, Any]] = []

        for row in investigations:
            current_batch.append(row)
            if len(current_batch) >= ctx.batch_size:
                batches.append(current_batch)
                current_batch = []

        # Add remaining batch
        if current_batch:
            batches.append(current_batch)

        logger.info("Worker %d/%d: Processing %d batches", ctx.worker_id, ctx.total_workers, len(batches))

        # Process each batch sequentially within this worker
        for batch_idx, batch in enumerate(batches):
            batch_stats = await process_batch(ctx, batch, batch_idx, len(batches))
            stats.merge(batch_stats)

    return stats


async def process_investigations(  # pylint: disable=too-many-locals
    cur: psycopg.AsyncCursor[dict[str, Any]],
    client: ApiClient,
    config: Config,
) -> ProcessingStats:
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

    Returns:
        ProcessingStats.
    """
    tracer = trace.get_tracer(__name__)
    stats = ProcessingStats()
    with tracer.start_as_current_span("sql_to_arc.main.process_investigations"):
        # Step 1: Fetch all investigations
        logger.info("Fetching all investigations...")
        with tracer.start_as_current_span("sql_to_arc.main.process_investigations:db_fetch_investigations"):
            investigation_rows = await fetch_all_investigations(cur)
        logger.info("Found %d investigations", len(investigation_rows))

        if not investigation_rows:
            logger.info("No investigations found, nothing to process")
            return stats

        # Step 2: Fetch all studies for these investigations in bulk
        investigation_ids = [row["id"] for row in investigation_rows]
        logger.info("Fetching studies for %d investigations...", len(investigation_ids))
        with tracer.start_as_current_span(
            "sql_to_arc.main.process_investigations:db_fetch_studies",
            attributes={"investigation_count": len(investigation_ids)},
        ):
            studies_by_investigation = await fetch_studies_bulk(cur, investigation_ids)
        total_studies = sum(len(studies) for studies in studies_by_investigation.values())
        logger.info("Found %d studies", total_studies)
        stats.total_studies = total_studies

        # Step 3: Fetch all assays for these studies in bulk
        study_ids = [study["id"] for studies in studies_by_investigation.values() for study in studies]
        logger.info("Fetching assays for %d studies...", len(study_ids))
        with tracer.start_as_current_span(
            "sql_to_arc.main.process_investigations:db_fetch_assays", attributes={"study_count": len(study_ids)}
        ):
            assays_by_study = await fetch_assays_bulk(cur, study_ids)
        total_assays = sum(len(assays) for assays in assays_by_study.values())
        logger.info("Found %d assays", total_assays)
        stats.total_assays = total_assays

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
            tasks = []
            for worker_id, assigned_investigations in enumerate(worker_assignments):
                if not assigned_investigations:
                    continue

                ctx = WorkerContext(
                    client=client,
                    rdi=config.rdi,
                    studies_by_investigation=studies_by_investigation,
                    assays_by_study=assays_by_study,
                    batch_size=config.batch_size,
                    worker_id=worker_id + 1,
                    total_workers=num_workers,
                    executor=executor,
                )
                tasks.append(process_worker_investigations(ctx, assigned_investigations))

            results = await asyncio.gather(*tasks)
            for res in results:
                if isinstance(res, ProcessingStats):
                    stats.merge(res)

    return stats


async def run_conversion(config: Config) -> ProcessingStats:
    """Run the SQL-to-ARC conversion with the given configuration.

    Args:
        config: Configuration object.

    Returns:
        ProcessingStats.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("sql_to_arc.main.run_conversion"):
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
            return await process_investigations(cur, client, config)


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
    otlp_endpoint = str(config.otel.endpoint) if config.otel.endpoint else None
    _tracer_provider, tracer = initialize_tracing(
        service_name="sql_to_arc",
        otlp_endpoint=otlp_endpoint,
        log_console_spans=config.otel.log_console_spans,
    )

    with tracer.start_as_current_span("sql_to_arc.main.main"):
        logger.info("Starting SQL-to-ARC conversion with config: %s", args.config)

        try:
            start_time = time.perf_counter()
            stats = await run_conversion(config)
            end_time = time.perf_counter()
            stats.duration_seconds = end_time - start_time

            logger.info("SQL-to-ARC conversion completed. Report:")
            print(
                stats.to_jsonld(rdi_identifier=config.rdi, rdi_url=config.rdi_url)
            )  # Print to stdout as requested for report

            # Log final summary
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
