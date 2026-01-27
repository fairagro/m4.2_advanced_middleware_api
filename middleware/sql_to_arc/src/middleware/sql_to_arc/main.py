"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import concurrent.futures
import json
import logging
import multiprocessing
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

from arctrl import (  # type: ignore[import-untyped]
    ARC,
    ArcTable,
    CompositeCell,
    CompositeHeader,
    IOType,
    OntologyAnnotation,
)
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, ValidationError

from middleware.api_client import ApiClient, ApiClientError
from middleware.shared.config.config_wrapper import ConfigWrapper
from middleware.shared.config.logging import configure_logging
from middleware.shared.tracing import initialize_tracing
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.database import Database
from middleware.sql_to_arc.mapper import (
    map_assay,
    map_contact,
    map_investigation,
    map_publication,
    map_study,
)


class ArcBuildData(BaseModel):
    """Data bundle for building a single ARC."""

    investigation_row: dict[str, Any]
    studies: list[dict[str, Any]]
    assays: list[dict[str, Any]]
    contacts: list[dict[str, Any]]
    publications: list[dict[str, Any]]
    annotations: list[dict[str, Any]]

    model_config = ConfigDict(arbitrary_types_allowed=True)


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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


def _add_studies_to_arc(arc: ARC, study_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Add studies to ARC and return study map."""
    study_map = {}
    for s_row in study_rows:
        study = map_study(s_row)
        arc.AddRegisteredStudy(study)
        study_map[str(s_row["identifier"])] = study
    return study_map


def _add_assays_to_arc(arc: ARC, assay_rows: list[dict[str, Any]], study_map: dict[str, Any]) -> dict[str, Any]:
    """Add assays to ARC, link to studies, and return assay map."""
    assay_map = {}
    for a_row in assay_rows:
        assay = map_assay(a_row)
        arc.AddAssay(assay)
        assay_map[str(a_row["identifier"])] = assay

        # Link Assay to Studies
        study_ref_json = a_row.get("study_ref")
        if not study_ref_json:
            continue

        try:
            study_refs = json.loads(study_ref_json)
            if isinstance(study_refs, list):
                for s_ref in study_refs:
                    if s_ref in study_map:
                        study_map[s_ref].RegisterAssay(assay.Identifier)
        except json.JSONDecodeError:
            pass

    return assay_map


def _add_contacts_to_arc(
    arc: ARC,
    inv_id: str,
    contacts: list[dict[str, Any]],
    study_map: dict[str, Any],
    assay_map: dict[str, Any],
) -> None:
    """Add contacts to investigation, studies, and assays."""
    # Investigation contacts
    inv_contacts = [
        c for c in contacts if c.get("investigation_ref") == inv_id and c.get("target_type") == "investigation"
    ]
    for c_row in inv_contacts:
        arc.Contacts.append(map_contact(c_row))

    # Study contacts
    for s_id, study in study_map.items():
        stu_contacts = [
            c
            for c in contacts
            if c.get("investigation_ref") == inv_id and c.get("target_type") == "study" and c.get("target_ref") == s_id
        ]
        for c_row in stu_contacts:
            study.Contacts.append(map_contact(c_row))

    # Assay contacts
    for a_id, assay in assay_map.items():
        ass_contacts = [
            c
            for c in contacts
            if c.get("investigation_ref") == inv_id and c.get("target_type") == "assay" and c.get("target_ref") == a_id
        ]
        for c_row in ass_contacts:
            assay.Performers.append(map_contact(c_row))


def _add_publications_to_arc(
    arc: ARC, inv_id: str, publications: list[dict[str, Any]], study_map: dict[str, Any]
) -> None:
    """Add publications to investigation and studies."""
    # Investigation publications
    inv_pubs = [
        p for p in publications if p.get("investigation_ref") == inv_id and p.get("target_type") == "investigation"
    ]
    for p_row in inv_pubs:
        arc.Publications.append(map_publication(p_row))

    # Study publications
    for s_id, study in study_map.items():
        stu_pubs = [
            p
            for p in publications
            if p.get("investigation_ref") == inv_id and p.get("target_type") == "study" and p.get("target_ref") == s_id
        ]
        for p_row in stu_pubs:
            study.Publications.append(map_publication(p_row))


def _build_arc_table(t_name: str, rows: list[dict[str, Any]]) -> ArcTable | None:
    """Build an ArcTable from flat database rows."""
    if not rows:
        return None

    table = ArcTable.init(t_name)

    # Determine max row index
    max_row_idx = max((cast(int, r.get("row_index", 0)) for r in rows), default=-1)
    if max_row_idx < 0:
        return None

    # Group cells by column definition
    def get_col_key(r: dict[str, Any]) -> tuple:
        return (
            r.get("column_type"),
            r.get("column_io_type"),
            r.get("column_value"),
            r.get("column_annotation_term"),
            r.get("column_annotation_uri"),
            r.get("column_annotation_version"),
            r.get("column_name"),  # Fallback for simple tests
        )

    col_keys: list[tuple] = []
    seen_keys = set()
    col_to_rows: dict[tuple, dict[int, dict[str, Any]]] = defaultdict(dict)

    for r in rows:
        key = get_col_key(r)
        if key not in seen_keys:
            col_keys.append(key)
            seen_keys.add(key)
        col_to_rows[key][cast(int, r.get("row_index", 0))] = r

    for key in col_keys:
        c_type, c_io, c_val, c_ann_term, c_ann_uri, c_ann_ver, c_name = key

        # Build Header
        header = None
        oa = OntologyAnnotation(c_ann_term or "", c_ann_uri or "", c_ann_ver or "")

        try:
            if c_type == "input":
                header = CompositeHeader.input(IOType.of_string(c_io or "source_name"))
            elif c_type == "output":
                header = CompositeHeader.output(IOType.of_string(c_io or "sample_name"))
            elif c_type == "characteristic":
                header = CompositeHeader.characteristic(oa)
            elif c_type == "factor":
                header = CompositeHeader.factor(oa)
            elif c_type == "parameter":
                header = CompositeHeader.parameter(oa)
            elif c_type == "component":
                header = CompositeHeader.component(oa)
            elif c_type == "comment":
                header = CompositeHeader.comment(c_val or "")
            elif c_type == "performer":
                header = CompositeHeader.performer()
            elif c_type == "date":
                header = CompositeHeader.date()
            elif c_name:
                # Fallback
                header = CompositeHeader.OfHeaderString(c_name)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to create header for type %s: %s", c_type, e)
            continue

        if not header:
            continue

        # Build Cells for this column
        col_cells = []
        rows_map = col_to_rows[key]
        for idx in range(max_row_idx + 1):
            cell_row = rows_map.get(idx)
            if not cell_row:
                col_cells.append(CompositeCell.free_text(""))
                continue

            cv = cell_row.get("cell_value")
            cat = cell_row.get("cell_annotation_term")
            cau = cell_row.get("cell_annotation_uri")
            cav = cell_row.get("cell_annotation_version")
            v = cell_row.get("value")  # Fallback for old/simple tests

            # Unitized cell?
            if cv is not None and cat is not None:
                col_cells.append(CompositeCell.unitized(str(cv), OntologyAnnotation(cat, cau or "", cav or "")))
            elif cat is not None:
                col_cells.append(CompositeCell.term(OntologyAnnotation(cat, cau or "", cav or "")))
            elif cv is not None:
                if header.IsTermColumn:
                    col_cells.append(CompositeCell.term(OntologyAnnotation(str(cv), "", "")))
                else:
                    col_cells.append(CompositeCell.free_text(str(cv)))
            elif v is not None:
                if header.IsTermColumn:
                    col_cells.append(CompositeCell.term(OntologyAnnotation(str(v), "", "")))
                else:
                    col_cells.append(CompositeCell.free_text(str(v)))
            else:
                col_cells.append(CompositeCell.free_text(""))

        table.AddColumn(header, col_cells)

    return table


def _process_annotation_tables(
    inv_id: str, annotations: list[dict[str, Any]], study_map: dict[str, Any], assay_map: dict[str, Any]
) -> None:
    """Process and add annotation tables."""
    tables_groups = defaultdict(list)
    for ann in annotations:
        if ann.get("investigation_ref") == inv_id:
            key = (ann.get("target_type"), ann.get("target_ref"), ann.get("table_name"))
            tables_groups[key].append(ann)

    for (t_type, t_ref, t_name), rows in tables_groups.items():
        if not t_name:
            continue

        target = None
        if t_type == "study" and isinstance(t_ref, str):
            target = study_map.get(t_ref)
        elif t_type == "assay" and isinstance(t_ref, str):
            target = assay_map.get(t_ref)

        if target:
            table = _build_arc_table(t_name, rows)
            if table:
                target.AddTable(table)


def build_single_arc_task(data: ArcBuildData) -> ARC:
    """Build a single ARC object from data.

    This function is designed to run in a separate process.
    """
    inv_id = str(data.investigation_row["identifier"])

    # Map Investigation and create ARC
    arc_inv = map_investigation(data.investigation_row)
    arc = ARC.from_arc_investigation(arc_inv)

    # Identify relevant studies and assays
    relevant_studies = [s for s in data.studies if s.get("investigation_ref") == inv_id]
    relevant_assays = [a for a in data.assays if a.get("investigation_ref") == inv_id]

    # Add studies and assays
    study_map = _add_studies_to_arc(arc, relevant_studies)
    assay_map = _add_assays_to_arc(arc, relevant_assays, study_map)

    # Add contacts and publications
    _add_contacts_to_arc(arc, inv_id, data.contacts, study_map, assay_map)
    _add_publications_to_arc(arc, inv_id, data.publications, study_map)

    # Process annotation tables
    _process_annotation_tables(inv_id, data.annotations, study_map, assay_map)

    return arc


class WorkerContext(BaseModel):
    """Context data for a worker process."""

    client: Any  # ApiClient, but Any to allow mocking
    rdi: str
    studies_by_inv: dict[str, list[dict[str, Any]]]
    assays_by_inv: dict[str, list[dict[str, Any]]]
    contacts_by_inv: dict[str, list[dict[str, Any]]]
    pubs_by_inv: dict[str, list[dict[str, Any]]]
    anns_by_inv: dict[str, list[dict[str, Any]]]
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


async def run_conversion(config: Config) -> ProcessingStats:
    """Run the conversion."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("run_conversion"):
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
