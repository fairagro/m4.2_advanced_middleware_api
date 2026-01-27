"""Orchestration and worker management for the SQL-to-ARC conversion process."""

import asyncio
import concurrent.futures
import logging
import multiprocessing
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any, cast

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.api_client import ApiClient, ApiClientError
from middleware.sql_to_arc.builder import build_single_arc_task
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.database import Database
from middleware.sql_to_arc.models import ArcBuildData, WorkerContext
from middleware.sql_to_arc.stats import ProcessingStats

logger = logging.getLogger(__name__)


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
            "upload_batch", attributes={"count": len(valid_arcs), "rdi": ctx.rdi, "worker_id": ctx.worker_id}
        ):
            response = await ctx.client.create_or_update_arcs(
                rdi=ctx.rdi,
                arcs=valid_arcs,
            )
        logger.info("%s: Upload request finished. API reported %d successful ARCs.", batch_info, len(response.arcs))

        # Log individual ARC results
        successful_ids = {a.id for a in response.arcs}
        for arc_response in response.arcs:
            logger.info("API response for ARC: id=%s, status=success", arc_response.id)

        if len(response.arcs) < len(valid_arcs):
            logger.warning(
                "%s: Only %d/%d ARCs were successfully processed by API.",
                batch_info,
                len(response.arcs),
                len(valid_arcs),
            )

            for arc in valid_arcs:
                identifier = getattr(arc, "Identifier", None)
                if identifier:
                    if identifier not in successful_ids:
                        logger.info("API response for ARC: id=%s, status=failed", identifier)
                        stats.failed_datasets += 1
                        stats.failed_ids.append(identifier)
                else:
                    logger.error("%s: ARC with missing identifier failed upload", batch_info)
                    stats.failed_datasets += 1
                    stats.failed_ids.append("unknown_id")

    except (ConnectionError, TimeoutError, ApiClientError) as e:
        logger.error("%s: Failed to upload batch: %s", batch_info, e, exc_info=True)
        stats.failed_datasets += len(valid_arcs)
        for row in valid_rows:
            stats.failed_ids.append(str(row["identifier"]))


async def _build_and_upload_single_arc(
    ctx: WorkerContext,
    investigation: dict[str, Any],
    stats: ProcessingStats,
    inv_id: str,
    inv_info: str,
) -> None:
    """Build a single ARC and upload it."""
    # Prepare data bundle for this investigation
    build_data = ArcBuildData(
        investigation_row=investigation,
        studies=ctx.studies_by_inv.get(inv_id, []),
        assays=ctx.assays_by_inv.get(inv_id, []),
        contacts=ctx.contacts_by_inv.get(inv_id, []),
        publications=ctx.pubs_by_inv.get(inv_id, []),
        annotations=ctx.anns_by_inv.get(inv_id, []),
    )

    # Build ARC in executor
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(ctx.executor, build_single_arc_task, build_data)

        if result is None:
            logger.error("%s: Build returned None for investigation %s", inv_info, inv_id)
            stats.failed_datasets += 1
            stats.failed_ids.append(inv_id)
            return

        arc = cast(ARC, result)
        arc_id = getattr(arc, "Identifier", "unknown")

        # Serialize ARC to JSON and calculate size
        try:
            arc_json = arc.ToROCrateJsonString()
            json_size_kb = len(arc_json.encode("utf-8")) / 1024
            logger.info("ARC JSON created: id=%s, size=%.2fKB", arc_id, json_size_kb)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to serialize ARC %s for size calculation: %s", arc_id, e)

        # Upload single ARC
        await _upload_and_update_stats(ctx, [arc], [investigation], stats, inv_info)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("%s: Failed to build ARC for investigation %s: %s", inv_info, inv_id, e)
        stats.failed_datasets += 1
        stats.failed_ids.append(inv_id)


async def process_investigation(
    ctx: WorkerContext,
    investigation: dict[str, Any],
    inv_idx: int,
    total_investigations: int,
) -> ProcessingStats:
    """Process a single investigation."""
    stats = ProcessingStats()
    tracer = trace.get_tracer(__name__)
    inv_id = str(investigation["identifier"])
    inv_info = f"Worker {ctx.worker_id}/{ctx.total_workers}, Investigation {inv_idx + 1}/{total_investigations}"

    with tracer.start_as_current_span(
        "build_investigation",
        attributes={"investigation_id": inv_id, "worker_id": ctx.worker_id, "inv_idx": inv_idx},
    ):
        logger.info("%s: Building ARC for investigation %s...", inv_info, inv_id)
        await _build_and_upload_single_arc(ctx, investigation, stats, inv_id, inv_info)

    return stats


async def process_worker_investigations(
    ctx: WorkerContext,
    investigations: list[dict[str, Any]],
) -> ProcessingStats:
    """Process a list of investigations assigned to this worker."""
    stats = ProcessingStats()
    if not investigations:
        return stats

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        "process_worker",
        attributes={"worker_id": ctx.worker_id, "investigation_count": len(investigations), "rdi": ctx.rdi},
    ):
        logger.info(
            "Worker %d/%d processing %d investigations...",
            ctx.worker_id,
            ctx.total_workers,
            len(investigations),
        )

        for idx, investigation in enumerate(investigations):
            inv_stats = await process_investigation(ctx, investigation, idx, len(investigations))
            stats.merge(inv_stats)

    return stats


async def _fetch_and_group_related_data(
    db: Database, investigation_ids: list[str]
) -> tuple[dict, dict, dict, dict, dict, int, int]:
    """Fetch related data in bulk and group by investigation ID."""
    logger.info("Fetching related data (studies, assays, contacts, etc.)...")

    async def collect(gen: AsyncGenerator[dict[str, Any], None]) -> list[dict[str, Any]]:
        return [row async for row in gen]

    # TODO: also here we're using lists, so generators or cursors
    study_rows = await collect(db.stream_studies(investigation_ids))
    assay_rows = await collect(db.stream_assays(investigation_ids))
    contact_rows = await collect(db.stream_contacts(investigation_ids))
    pub_rows = await collect(db.stream_publications(investigation_ids))
    ann_rows = await collect(db.stream_annotation_tables(investigation_ids))

    def group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        m = defaultdict(list)
        for r in rows:
            m[str(r["investigation_ref"])].append(r)
        return dict(m)

    # TODO: do not return such a big tuple, use a pydantic model instead
    return (
        group(study_rows),
        group(assay_rows),
        group(contact_rows),
        group(pub_rows),
        group(ann_rows),
        len(study_rows),
        len(assay_rows),
    )


def _prepare_worker_assignments(num_workers: int, rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split investigations into buckets for workers."""
    assignments: list[list[dict[str, Any]]] = [[] for _ in range(num_workers)]
    for idx, investigation in enumerate(rows):
        assignments[idx % num_workers].append(investigation)
    return assignments


async def _create_worker_tasks(
    executor: concurrent.futures.ProcessPoolExecutor,
    client: ApiClient,
    config: Config,
    worker_assignments: list[list[dict[str, Any]]],
    data_maps: tuple,
) -> list[Any]:
    """Create tasks for each worker."""
    tasks = []
    num_workers = len(worker_assignments)
    for worker_id, assigned in enumerate(worker_assignments):
        if not assigned:
            continue
        ctx = WorkerContext(
            client=client,
            rdi=config.rdi,
            studies_by_inv=data_maps[0],
            assays_by_inv=data_maps[1],
            contacts_by_inv=data_maps[2],
            pubs_by_inv=data_maps[3],
            anns_by_inv=data_maps[4],
            worker_id=worker_id + 1,
            total_workers=num_workers,
            executor=executor,
        )
        tasks.append(process_worker_investigations(ctx, assigned))
    return tasks


async def _execute_distributed_workers(
    client: ApiClient,
    config: Config,
    investigation_rows: list[dict[str, Any]],
    data_maps: tuple,
) -> ProcessingStats:
    """Distribute investigations to workers and collect results."""
    stats = ProcessingStats()
    num_workers = config.max_concurrent_arc_builds
    worker_assignments = _prepare_worker_assignments(num_workers, investigation_rows)

    mp_context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers, mp_context=mp_context) as executor:
        tasks = await _create_worker_tasks(executor, client, config, worker_assignments, data_maps)
        results = await asyncio.gather(*tasks)
        for res in results:
            if isinstance(res, ProcessingStats):
                stats.merge(res)
    return stats


async def process_investigations(
    db: Database,
    client: ApiClient,
    config: Config,
) -> ProcessingStats:
    """Fetch investigations from DB and process them."""
    tracer = trace.get_tracer(__name__)
    stats = ProcessingStats()
    with tracer.start_as_current_span("process_investigations"):
        logger.info("Fetching investigations (limit=%s)...", config.debug_limit)
        # TODO: this looks like it fetches all investigations at once, although we've switched to database cursors
        # Maybe it would be better to use an async generator here instead?
        investigation_rows = [row async for row in db.stream_investigations(limit=config.debug_limit)]
        logger.info("Found %d investigations", len(investigation_rows))
        stats.found_datasets = len(investigation_rows)

        if not investigation_rows:
            logger.info("No investigations found, nothing to process")
            return stats

        # TODO: also this seems to contract a one investigation at a time pattern,
        inv_ids = [str(row["identifier"]) for row in investigation_rows]
        maps_and_counts = await _fetch_and_group_related_data(db, inv_ids)

        stats.total_studies = maps_and_counts[5]
        stats.total_assays = maps_and_counts[6]

        worker_stats = await _execute_distributed_workers(client, config, investigation_rows, maps_and_counts[:5])
        stats.merge(worker_stats)

    return stats
