"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import concurrent.futures
import gc
import json
import logging
import multiprocessing
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

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
            "status": ("schema:CompletedActionStatus" if self.failed_datasets == 0 else "schema:FailedActionStatus"),
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


async def stream_investigation_datasets(
    cur: psycopg.AsyncCursor[dict[str, Any]], batch_size: int = 100
) -> "AsyncGenerator[tuple[dict[str, Any], list[dict[str, Any]], dict[int, list[dict[str, Any]]]], None]":
    """Stream investigation datasets (inv + studies + assays) in batches.

    This avoids loading the entire database into memory.

    Args:
        cur: Database cursor.
        batch_size: Number of investigations to fetch and process details for at once.

    Yields:
        Tuple of (investigation_row, studies_list, assays_by_study_dict).
    """
    # Use a server-side cursor if it has a name, otherwise it's client-side.
    # To be safe and compatible, we'll just execute and chunk the results if needed,
    # or rely on the cursor being a server-side one from the caller.
    await cur.execute('SELECT id, title, description, submission_time, release_time FROM "ARC_Investigation"')

    while True:
        rows = await cur.fetchmany(batch_size)
        if not rows:
            break

        investigation_ids = [row["id"] for row in rows]

        if not cur.connection:
            raise RuntimeError("Cursor has no connection attached")

        # Fetch studies for this batch using a separate cursor
        # We MUST use a separate cursor because executing on 'cur' would Close
        # the current result set (investigations) if it's not fully consumed/server-side.
        # Even with server-side cursors, it's safer to use a dedicated cursor for nested queries.
        async with cur.connection.cursor(row_factory=dict_row) as detail_cur:
            await detail_cur.execute(
                "SELECT id, investigation_id, title, description, submission_time, release_time "
                'FROM "ARC_Study" WHERE investigation_id = ANY(%s)',
                (investigation_ids,),
            )
            study_rows = await detail_cur.fetchall()
            studies_by_inv: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for s in study_rows:
                studies_by_inv[s["investigation_id"]].append(s)

            # Fetch assays for these studies
            study_ids = [s["id"] for s in study_rows]
            assays_by_study: dict[int, list[dict[str, Any]]] = defaultdict(list)
            if study_ids:
                await detail_cur.execute(
                    'SELECT id, study_id, measurement_type, technology_type FROM "ARC_Assay" WHERE study_id = ANY(%s)',
                    (study_ids,),
                )
                assay_rows = await detail_cur.fetchall()
                for a in assay_rows:
                    assays_by_study[a["study_id"]].append(a)

        # Re-fetch investigation rows if necessary? No, we have them in 'rows'.
        # But wait, we used the cursor for studies/assays!
        # CAUTION: If using a single connection/cursor, we MUST fetch all studies/assays
        # before we can use the cursor again for the next batch of investigations.
        # This is why we use fetchmany(batch_size) and then do the detail queries.

        for inv_row in rows:
            inv_id = inv_row["id"]
            yield inv_row, studies_by_inv[inv_id], assays_by_study


# Removed fetch_studies_bulk and fetch_assays_bulk as they are now integrated into stream_investigation_datasets


def build_arc_for_investigation(
    investigation_row: dict[str, Any],
    studies: list[dict[str, Any]],
    assays_by_study: dict[int, list[dict[str, Any]]],
) -> str:
    """Build a single ARC for an investigation (CPU-bound operation for ProcessPoolExecutor).

    This function is designed to be called in a separate process and returns
     the JSON representation to minimize memory footprint in the main process.

    Args:
        investigation_row: Investigation database row.
        studies: List of studies for this investigation.
        assays_by_study: Dictionary mapping study_id to list of assays.

    Returns:
        JSON string representation of the ARC.
    """
    try:
        # Filter assays for these studies
        relevant_assays = {s["id"]: assays_by_study.get(s["id"], []) for s in studies}

        # Build ArcInvestigation
        arc_investigation = build_single_arc_task(investigation_row, studies, relevant_assays)

        # Wrap in ARC container
        arc = ARC.from_arc_investigation(arc_investigation)

        # Serialize immediately in the worker process
        json_str: str = arc.ToROCrateJsonString()

        # Explicitly clean up memory before returning
        del arc
        del arc_investigation
        gc.collect()

        return json_str
    except Exception:
        gc.collect()
        raise


class WorkerContext(BaseModel):
    """Context data for a worker process."""

    client: Any  # ApiClient, but Any to allow mocking
    rdi: str
    executor: Any  # ProcessPoolExecutor is not Pydantic-friendly easily, so Any

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DatasetContext(BaseModel):
    """Context for a single investigation dataset (investigation, studies, assays)."""

    investigation_row: dict[str, Any]
    studies: list[dict[str, Any]]
    assays_by_study: dict[int, list[dict[str, Any]]]

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def process_single_dataset(
    ctx: WorkerContext,
    dataset_ctx: DatasetContext,
    semaphore: asyncio.Semaphore,
    stats: ProcessingStats,
) -> None:
    """Process a single investigation: Build -> Serialize -> Log -> Upload.

    Args:
        ctx: Worker context (client, executor, etc).
        dataset_ctx: DatasetContext containing investigation, studies, and assays.
        semaphore: Semaphore to limit concurrent active tasks.
        stats: Stats object to update (mutable).
    """
    log_prefix = f"[InvID: {dataset_ctx.investigation_row['id']}]"

    # Acquire semaphore to limit concurrency
    async with semaphore:
        try:
            # 1. Prepare data (already gathered by stream)
            # Count details for stats/logging
            num_studies = len(dataset_ctx.studies)
            num_assays = sum(len(dataset_ctx.assays_by_study.get(s["id"], [])) for s in dataset_ctx.studies)
            stats.total_studies += num_studies
            stats.total_assays += num_assays

            logger.info(
                "%s Starting ARC build. Content: %d studies, %d assays.",
                log_prefix,
                num_studies,
                num_assays,
            )

            # 2. Build & Serialize ARC (CPU-bound) -> Offload to ProcessPool
            # We return the JSON string directly from the worker to allow early GC of ARC objects
            json_str = await asyncio.get_event_loop().run_in_executor(
                ctx.executor,
                build_arc_for_investigation,
                dataset_ctx.investigation_row,
                dataset_ctx.studies,
                dataset_ctx.assays_by_study,
            )

            if not json_str:
                logger.error("%s ARC build/serialization failed", log_prefix)
                stats.failed_datasets += 1
                stats.failed_ids.append(str(dataset_ctx.investigation_row["id"]))
                return

            logger.info(
                "%s ARC build & serialization complete. Payload size: %.2f MB. Uploading...",
                log_prefix,
                len(json_str.encode("utf-8")) / (1024 * 1024),
            )

            # 4. Upload (IO-bound)
            response = await ctx.client.create_or_update_arc(
                rdi=ctx.rdi,
                arc=json.loads(json_str),
            )
            logger.info(
                "%s ARC uploaded successfully.",
                log_prefix,
            )

        except (ApiClientError, psycopg.Error, OSError) as e:
            logger.error("%s Processing failed: %s", log_prefix, e)
            stats.failed_datasets += 1
            stats.failed_ids.append(str(dataset_ctx.investigation_row["id"]))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("%s Unexpected error: %s", log_prefix, e, exc_info=True)
            stats.failed_datasets += 1
            stats.failed_ids.append(str(dataset_ctx.investigation_row["id"]))


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
    stats = ProcessingStats()
    with trace.get_tracer(__name__).start_as_current_span("sql_to_arc.main.process_investigations"):
        # Step 1: Initialize concurrency control
        semaphore = asyncio.Semaphore(config.max_concurrent_tasks)
        logger.info(
            "Starting streaming processing: CPU_workers=%d, Max_tasks=%d",
            config.max_concurrent_arc_builds,
            config.max_concurrent_tasks,
        )

        # Use ProcessPoolExecutor for CPU offloading
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=config.max_concurrent_arc_builds, mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            ctx = WorkerContext(
                client=client,
                rdi=config.rdi,
                executor=executor,
            )

            # Step 2: Stream and spawn tasks
            # We use a set of tasks to keep track of running operations
            running_tasks: set[asyncio.Task] = set()

            async for item in stream_investigation_datasets(cur, batch_size=config.db_batch_size):
                stats.found_datasets += 1

                # Backlog Flow Control: Prevent reading too much from DB if workers are busy.
                # If we have reached the max number of concurrent tasks, wait for one to finish.
                # This keeps the memory footprint under control by stopping the stream producer.
                if len(running_tasks) >= config.max_concurrent_tasks:
                    await asyncio.wait(running_tasks, return_when=asyncio.FIRST_COMPLETED)

                dataset_ctx = DatasetContext(
                    investigation_row=item[0],
                    studies=item[1],
                    assays_by_study=item[2],
                )

                # Create the processing task
                # Note: process_single_dataset itself handles the semaphore
                task = asyncio.create_task(process_single_dataset(ctx, dataset_ctx, semaphore, stats))
                running_tasks.add(task)

                # Cleanup finished tasks periodically to keep memory low
                task.add_done_callback(running_tasks.discard)

            # Wait for all remaining tasks to finish
            if running_tasks:
                logger.info("Waiting for %d remaining tasks to complete...", len(running_tasks))
                await asyncio.gather(*running_tasks)

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
