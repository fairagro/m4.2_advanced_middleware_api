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
            "status": (
                "schema:CompletedActionStatus"
                if self.failed_datasets == 0
                else "schema:FailedActionStatus"
            ),
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


async def fetch_all_investigations(
    cur: psycopg.AsyncCursor[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fetch all investigations from the database.

    Args:
        cur: Database cursor.

    Returns:
        List of investigation rows.
    """
    await cur.execute(
        'SELECT id, title, description, submission_time, release_time '
        'FROM "ARC_Investigation"',  # LIMIT 10
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
        'SELECT id, study_id, measurement_type, technology_type '
        'FROM "ARC_Assay" WHERE study_id = ANY(%s)',
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
    worker_id: int
    total_workers: int
    executor: Any  # ProcessPoolExecutor is not Pydantic-friendly easily, so Any

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def process_single_dataset(
    ctx: WorkerContext,
    investigation_row: dict[str, Any],
    semaphore: asyncio.Semaphore,
    stats: ProcessingStats,
) -> None:
    """Process a single investigation: Build -> Serialize -> Log -> Upload.

    Args:
        ctx: Worker context (client, executor, etc).
        investigation_row: The investigation data.
        semaphore: Semaphore to limit concurrent active tasks.
        stats: Stats object to update (mutable).
    """
    inv_id = investigation_row["id"]
    log_prefix = f"[InvID: {inv_id}]"

    # Acquire semaphore to limit concurrency
    async with semaphore:
        try:
            # 1. Gather data (Memory-bound, fast)
            studies = ctx.studies_by_investigation.get(inv_id, [])
            relevant_assays = {s["id"]: ctx.assays_by_study.get(s["id"], []) for s in studies}

            # Count details for logging
            num_studies = len(studies)
            num_assays = sum(len(a) for a in relevant_assays.values())
            logger.info(
                "%s Starting ARC build. Content: %d studies, %d assays.",
                log_prefix,
                num_studies,
                num_assays,
            )

            # 2. Build ARC (CPU-bound) -> Offload to ProcessPool
            loop = asyncio.get_event_loop()
            arc = await loop.run_in_executor(
                ctx.executor,
                build_arc_for_investigation,
                investigation_row,
                studies,
                ctx.assays_by_study,
            )

            if not arc:
                logger.error("%s ARC build returned None", log_prefix)
                stats.failed_datasets += 1
                stats.failed_ids.append(str(inv_id))
                return

            # Retrieve Identifier from ARC for correlation
            arc_identifier = getattr(arc, "Identifier", str(inv_id))
            # Update prefix with real ARC ID if available
            log_prefix = f"[ARC: {arc_identifier}]"

            # 3. Serialize (CPU-bound) -> Offload to ProcessPool
            # We serialize here to:
            #   a) Get the size for logging
            #   b) Pass dict to ApiClient (avoiding double serialization)
            json_str = await loop.run_in_executor(None, arc.ToROCrateJsonString)
            serialized_arc = json.loads(json_str)

            # Calculate size in bytes
            size_bytes = len(json_str.encode("utf-8"))
            size_mb = size_bytes / (1024 * 1024)
            logger.info(
                "%s Serialization complete. Payload size: %.2f MB. Uploading...",
                log_prefix,
                size_mb,
            )

            # 4. Upload (IO-bound)
            # Use new create_or_update_arc method
            response = await ctx.client.create_or_update_arc(
                rdi=ctx.rdi,
                arc=serialized_arc,
            )
            logger.info(
                "%s Upload successful. API confirmed %d ARC(s) processed.",
                log_prefix,
                len(response.arcs),
            )

        except (ApiClientError, psycopg.Error, OSError) as e:
            logger.error("%s Processing failed: %s", log_prefix, e)
            stats.failed_datasets += 1
            stats.failed_ids.append(str(inv_id))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("%s Unexpected error: %s", log_prefix, e, exc_info=True)
            stats.failed_datasets += 1
            stats.failed_ids.append(str(inv_id))


async def process_investigations(
    cur: psycopg.AsyncCursor[dict[str, Any]],
    client: ApiClient,
    config: Config,
) -> ProcessingStats:
    """Fetch investigations from DB and process them concurrently.

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
        # Step 1: Fetch all data (bulk)
        logger.info("Fetching all investigations...")
        investigation_rows = await fetch_all_investigations(cur)
        stats.found_datasets = len(investigation_rows)
        logger.info("Found %d investigations", stats.found_datasets)

        if not investigation_rows:
            return stats

        # Fetch studies
        investigation_ids = [row["id"] for row in investigation_rows]
        studies_by_investigation = await fetch_studies_bulk(cur, investigation_ids)
        stats.total_studies = sum(len(s) for s in studies_by_investigation.values())

        # Fetch assays
        study_ids = [s["id"] for studies in studies_by_investigation.values() for s in studies]
        assays_by_study = await fetch_assays_bulk(cur, study_ids)
        stats.total_assays = sum(len(a) for a in assays_by_study.values())

        logger.info(
            "Data fetch complete. Total: %d studies, %d assays.",
            stats.total_studies,
            stats.total_assays,
        )

        # Step 2: Dynamic Concurrency with Producer-Consumer pattern
        # Limit max concurrent tasks (Build+Serialize+Upload)
        limit = config.max_concurrent_arc_builds
        semaphore = asyncio.Semaphore(limit)
        logger.info("Starting processing with max_concurrent_tasks=%d", limit)

        # Use ProcessPoolExecutor for CPU offloading
        # "spawn" context is safer for mix of asyncio/multiprocessing
        mp_context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=limit, mp_context=mp_context
        ) as executor:
            # Create shared context (stateless parts)
            ctx = WorkerContext(
                client=client,
                rdi=config.rdi,
                studies_by_investigation=studies_by_investigation,
                assays_by_study=assays_by_study,
                worker_id=0,  # Not used in new dynamic model
                total_workers=limit,
                executor=executor,
            )

            # Create tasks
            tasks = [
                process_single_dataset(ctx, row, semaphore, stats)
                for row in investigation_rows
            ]

            # Run all tasks
            await asyncio.gather(*tasks)

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
                logger.info(
                    "Conversion finished successfully. %d datasets processed.",
                    stats.found_datasets,
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.critical("Fatal error during conversion process: %s", e, exc_info=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    asyncio.run(main())
